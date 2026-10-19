#!/usr/bin/env python3
"""Aris atproto bot.

Publishes each Scroll Press paper that has a DOI to the Press-owned atproto
account as three records:

  - pub.aris.scroll      the structured Press record (key = url_hash)
  - app.bsky.feed.post   a short announcement on the Press Bluesky account
  - network.cosmik.card  a Semble card (carries the DOI in its metadata)

It is stateless and writes only what has changed. Before writing, it reads the
records already in the account's repo and skips any that are byte-for-byte the
same as what it would write. Every record uses a deterministic key, and every
field is deterministic, so a record is rewritten only when its paper's metadata
actually changed (for example when the DOI lands). No local state, no database.

Reads only the public Press API for the paper list, so it does not import the
Press app and can run anywhere.

Usage:
    # Dry run. Prints the plan (create / update / unchanged), writes nothing.
    # With credentials it reads the repo so the plan is exact. Without them it
    # cannot check the current state and marks everything as a write.
    uv run python scripts/aris_atproto_bot.py

    # Actually write the records (requires credentials).
    ARIS_BOT_HANDLE=aris-pub.bsky.social ARIS_BOT_PASSWORD=<app-password> \
        uv run python scripts/aris_atproto_bot.py --post

    # Limit to one paper by url_hash (useful for a first real run).
    uv run python scripts/aris_atproto_bot.py --post --only a53f35091073

Environment:
    ARIS_BOT_HANDLE    the Press atproto handle, e.g. aris-pub.bsky.social
    ARIS_BOT_PASSWORD  an app password for that account
    ARIS_BOT_PDS       PDS host, default https://bsky.social
    ARIS_SITE          Press base URL, default https://scroll.press
"""

import hashlib
import os
import sys
import re
from datetime import datetime

import httpx

SITE = os.getenv("ARIS_SITE", "https://scroll.press").rstrip("/")
PDS = os.getenv("ARIS_BOT_PDS", "https://bsky.social").rstrip("/")

# Fetches run from GitHub Actions (datacenter IPs). A browser-like UA avoids
# naive bot-filtering on the sitemap and the per-scroll .json endpoints. If a
# fetch is still blocked (for example a Cloudflare IP challenge), list_scroll_urls
# raises with the response so the CI log shows exactly what came back, instead of
# silently returning an empty list.
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,text/html;q=0.9,*/*;q=0.8",
}

# base32-sortable alphabet used by atproto TIDs
_S32 = "234567abcdefghijklmnopqrstuvwxyz"


def _s32encode(value: int) -> str:
    out = ""
    for _ in range(13):
        out = _S32[value & 31] + out
        value >>= 5
    return out


def stable_tid(when: datetime, seed: str) -> str:
    """A valid, deterministic TID from a timestamp and a seed string.

    app.bsky.feed.post and network.cosmik.card require TID-format keys. Using
    the publish time plus a seed off url_hash gives a key that is stable across
    runs and sorts by publish date rather than run time.
    """
    micros = int(when.timestamp() * 1_000_000) & ((1 << 53) - 1)
    clock_id = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) & 0x3FF
    return _s32encode(((micros << 10) | clock_id) & ((1 << 63) - 1))


def _norm(value):
    """Drop every key starting with $ (atproto type markers) so two records
    compare on content only."""
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in value.items() if not k.startswith("$")}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


# ---- Press API ------------------------------------------------------------


def list_scroll_urls() -> list[str]:
    url = f"{SITE}/sitemap.xml"
    resp = httpx.get(url, timeout=30, headers=BROWSER_HEADERS, follow_redirects=True)
    body = resp.text
    snippet = body[:300].replace("\n", " ")
    if resp.status_code != 200:
        raise RuntimeError(
            f"sitemap fetch failed: {resp.status_code} "
            f"(content-type {resp.headers.get('content-type', '')!r}) from {url}; "
            f"first 300 chars: {snippet!r}"
        )
    if "<loc>" not in body and "<urlset" not in body:
        raise RuntimeError(
            f"sitemap is not the expected XML (content-type "
            f"{resp.headers.get('content-type', '')!r}) from {url}; "
            f"this is usually a bot challenge page; first 300 chars: {snippet!r}"
        )
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
    pattern = re.compile(rf"{re.escape(SITE)}/\d{{4}}/[^/]+$")
    urls = sorted({u for u in locs if pattern.fullmatch(u)})
    if not urls:
        raise RuntimeError(
            f"sitemap had {len(locs)} <loc> entries but none matched "
            f"{SITE}/YYYY/<slug>; first 300 chars: {snippet!r}"
        )
    return urls


def fetch_meta(url: str) -> dict:
    resp = httpx.get(f"{url}.json", timeout=30, headers=BROWSER_HEADERS, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


# ---- Record builders (all fields deterministic) ---------------------------


def _authors_objs(authors: str) -> list[dict]:
    return [{"displayName": a.strip()} for a in (authors or "").split(",") if a.strip()]


def scroll_record(m: dict) -> dict:
    record = {
        "$type": "pub.aris.scroll",
        "title": m["title"],
        "authors": _authors_objs(m["authors"]),
        "abstract": m["abstract"],
        "canonicalUrl": m["canonical_url"],
        "urlHash": m["url_hash"],
        "contentHash": m["html_sha256"],
        "publishedAt": m["published_at"],
        "license": m["license"],
        "doi": m["doi"],
        "version": m["version"],
        "publicationYear": m["year"],
        "format": "interactive_html",
    }
    if m.get("keywords"):
        record["keywords"] = m["keywords"]
    return record


def bsky_record(m: dict) -> dict:
    text = f"New on Scroll Press: {m['title']}"
    if len(text) > 300:
        text = text[:297] + "..."
    return {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": m["published_at"],
        "embed": {
            "$type": "app.bsky.embed.external",
            "external": {
                "uri": m["canonical_url"],
                "title": m["title"],
                "description": (m["abstract"] or "")[:290],
            },
        },
    }


def card_record(m: dict) -> dict:
    return {
        "$type": "network.cosmik.card",
        "type": "URL",
        "url": m["canonical_url"],
        "createdAt": m["published_at"],
        "content": {
            "$type": "network.cosmik.card#urlContent",
            "url": m["canonical_url"],
            "metadata": {
                "title": m["title"],
                "description": (m["abstract"] or "")[:500],
                "author": m["authors"],
                "publishedDate": m["published_at"],
                "siteName": "Scroll Press",
                "type": "article",
                "doi": m["doi"],
            },
        },
    }


# ---- atproto ---------------------------------------------------------------


def login() -> tuple[str, str]:
    resp = httpx.post(
        f"{PDS}/xrpc/com.atproto.server.createSession",
        json={
            "identifier": os.environ["ARIS_BOT_HANDLE"],
            "password": os.environ["ARIS_BOT_PASSWORD"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["accessJwt"], data["did"]


def load_existing(jwt: str, did: str, collection: str) -> dict:
    """Map rkey -> stored record value for one collection, via listRecords."""
    out: dict = {}
    cursor = None
    while True:
        params = {"repo": did, "collection": collection, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = httpx.get(
            f"{PDS}/xrpc/com.atproto.repo.listRecords",
            params=params,
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("records", []):
            out[item["uri"].rsplit("/", 1)[-1]] = item["value"]
        cursor = data.get("cursor")
        if not cursor or not data.get("records"):
            return out


def put_record(jwt: str, did: str, collection: str, rkey: str, record: dict) -> str:
    resp = httpx.post(
        f"{PDS}/xrpc/com.atproto.repo.putRecord",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"repo": did, "collection": collection, "rkey": rkey, "record": record},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["uri"]


# ---- main ------------------------------------------------------------------

COLLECTIONS = ["pub.aris.scroll", "app.bsky.feed.post", "network.cosmik.card"]


def main() -> int:
    args = sys.argv[1:]
    do_post = "--post" in args
    only = None
    if "--only" in args:
        i = args.index("--only")
        if i + 1 >= len(args):
            print("usage: --only <url_hash>", file=sys.stderr)
            return 64
        only = args[i + 1]

    have_creds = bool(os.getenv("ARIS_BOT_HANDLE") and os.getenv("ARIS_BOT_PASSWORD"))
    if do_post and not have_creds:
        print("--post requires ARIS_BOT_HANDLE and ARIS_BOT_PASSWORD", file=sys.stderr)
        return 64

    jwt = did = None
    existing: dict = {c: {} for c in COLLECTIONS}
    if have_creds:
        jwt, did = login()
        for c in COLLECTIONS:
            existing[c] = load_existing(jwt, did, c)
    else:
        print("no credentials: cannot read current state, every record shown as a write")

    urls = list_scroll_urls()
    created = updated = unchanged = skipped = 0

    for url in urls:
        m = fetch_meta(url)
        if only and m.get("url_hash") != only:
            continue
        if not m.get("doi"):
            print(f"skip (no doi yet): {url}")
            skipped += 1
            continue

        url_hash = m["url_hash"]
        published = datetime.fromisoformat(m["published_at"])
        plan = [
            ("pub.aris.scroll", url_hash, scroll_record(m)),
            ("app.bsky.feed.post", stable_tid(published, "bsky:" + url_hash), bsky_record(m)),
            ("network.cosmik.card", stable_tid(published, "card:" + url_hash), card_record(m)),
        ]

        for collection, rkey, record in plan:
            current = existing.get(collection, {}).get(rkey)
            if current is not None and _norm(current) == _norm(record):
                unchanged += 1
                print(f"unchanged  {collection} {rkey}  ({m['title']})")
                continue
            action = "update" if current is not None else "create"
            if do_post:
                uri = put_record(jwt, did, collection, rkey, record)
                print(f"{action}  {collection} {rkey} -> {uri}")
            else:
                print(f"[dry-run] {action}  {collection} {rkey}  ({m['title']})")
            if action == "create":
                created += 1
            else:
                updated += 1

    print(f"\ncreate={created} update={updated} unchanged={unchanged} skipped_no_doi={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
