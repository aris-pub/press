#!/usr/bin/env python3
"""Add the Press link and the uploader's ORCID to already published Zenodo records.

For each published scroll with a minted DOI, reads the record's current metadata from
Zenodo, adds a related_identifiers entry pointing at the scroll's permanent Press URL,
and puts the uploader's ORCID on the uploader's own creator entry. All other metadata
fields are kept as they are.

The default is a dry run that prints what would change and writes nothing. Pass
--apply to write. Writing uses Zenodo's edit, update and publish actions on the
existing record, which changes metadata without creating a new version or a new DOI.

Usage:
    uv run python scripts/backfill_zenodo_metadata.py
    uv run python scripts/backfill_zenodo_metadata.py --scroll-id <uuid> --apply
    uv run python scripts/backfill_zenodo_metadata.py --apply
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Callable, Optional
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.config import get_base_url  # noqa: E402
from app.integrations.doi_service import merge_backfill_metadata  # noqa: E402
from app.integrations.zenodo import ZenodoClient, ZenodoError, get_zenodo_client  # noqa: E402
from app.models.scroll import Scroll  # noqa: E402


def _dump(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


async def backfill(
    db: AsyncSession,
    zenodo: ZenodoClient,
    base_url: str,
    apply: bool = False,
    scroll_id: Optional[UUID] = None,
    out: Callable[[str], None] = print,
) -> dict:
    """Run the backfill and return counts of updated, skipped and failed scrolls."""
    query = (
        select(Scroll)
        .options(selectinload(Scroll.user))
        .where(
            Scroll.status == "published",
            Scroll.doi_status == "minted",
            Scroll.zenodo_deposit_id.is_not(None),
        )
        .order_by(Scroll.published_at)
    )
    if scroll_id is not None:
        query = query.where(Scroll.id == scroll_id)
    scrolls = (await db.execute(query)).scalars().all()

    counts = {"would_update": 0, "updated": 0, "skipped": 0, "failed": 0}
    for scroll in scrolls:
        deposit_id = scroll.zenodo_deposit_id
        out(f"\n=== {scroll.title} (scroll {scroll.id}, deposit {deposit_id}, DOI {scroll.doi})")
        try:
            deposit = await zenodo.get_deposit(deposit_id)
        except ZenodoError as e:
            out(f"FAILED to read deposit: {e}")
            counts["failed"] += 1
            continue

        metadata = deposit.get("metadata") or {}
        merged = merge_backfill_metadata(metadata, scroll, scroll.user, base_url)
        if merged is None:
            out("Already has the Press link and ORCID, skipping.")
            counts["skipped"] += 1
            continue

        out("Current related_identifiers:")
        out(_dump(metadata.get("related_identifiers") or []))
        out("New related_identifiers:")
        out(_dump(merged.get("related_identifiers") or []))
        out("Current creators:")
        out(_dump(metadata.get("creators") or []))
        out("New creators:")
        out(_dump(merged.get("creators") or []))

        if not apply:
            counts["would_update"] += 1
            continue

        edit_started = False
        try:
            await zenodo.edit_deposit(deposit_id)
            edit_started = True
            await zenodo.update_deposit_metadata(deposit_id, merged)
            await zenodo.publish_deposit(deposit_id)
            out("Updated.")
            counts["updated"] += 1
        except ZenodoError as e:
            out(f"FAILED to update: {e}")
            counts["failed"] += 1
            # Leaving the record in an open edit session would block later edits.
            if edit_started:
                try:
                    await zenodo.discard_deposit_edit(deposit_id)
                    out("Discarded the edit session.")
                except ZenodoError as discard_error:
                    out(f"FAILED to discard the edit session: {discard_error}")

    out(f"\nDone. {counts}")
    return counts


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="write changes to Zenodo")
    parser.add_argument("--scroll-id", type=UUID, help="only process this scroll")
    parser.add_argument("--base-url", help="Press base URL, defaults to BASE_URL")
    args = parser.parse_args()

    base_url = (args.base_url or get_base_url()).rstrip("/")
    zenodo = get_zenodo_client()
    if zenodo is None:
        print("ZENODO_API_TOKEN and ZENODO_BASE_URL must be set.")
        return 1

    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN (nothing is written)'}")
    print(f"Press base URL: {base_url}")
    print(f"Zenodo: {zenodo.config.base_url}")

    if args.apply and ("localhost" in base_url or "127.0.0.1" in base_url):
        print("Refusing to write a localhost link to Zenodo. Set BASE_URL or --base-url.")
        await zenodo.close()
        return 1

    from app.database import AsyncSessionLocal

    db = AsyncSessionLocal()
    try:
        counts = await backfill(db, zenodo, base_url, apply=args.apply, scroll_id=args.scroll_id)
    finally:
        await db.close()
        await zenodo.close()
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
