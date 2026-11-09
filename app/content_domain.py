"""Serve paper files from {url_hash}.<CONTENT_DOMAIN>, a different site from Press.

A paper's scripts then run on another site, so they cannot use a reader's Press login
(docs/THREAT_MODEL.md). Requests to the content domain are mapped onto the existing paper
routes under /scroll/{url_hash}/paper/, so nothing else in Press can be reached there.
"""

import re
from urllib.parse import urlsplit

from app.config import get_base_url, get_content_domain

# url_hash is a hex prefix of the content hash. A DNS label holds at most 63 characters.
_HASH_LABEL = re.compile(r"^[0-9a-f]{1,63}$")
_DROPPED_HEADERS = {b"x-frame-options", b"set-cookie"}


def content_host_hash(host: str) -> str | None:
    """The url_hash a content domain host names, "" for a content domain host that names
    none, or None when the host is not on the content domain."""
    domain = get_content_domain()
    if not domain:
        return None
    host = host.split(":", 1)[0].strip().lower().rstrip(".")
    if host == domain:
        return ""
    if not host.endswith("." + domain):
        return None
    label = host[: -len(domain) - 1]
    return label if _HASH_LABEL.match(label) else ""


def paper_url(url_hash: str, path: str = "") -> str | None:
    """Where a published paper's files are served, or None if Press serves them itself."""
    domain = get_content_domain()
    if not domain or not _HASH_LABEL.match(url_hash):
        return None
    return f"{_scheme()}://{url_hash}.{domain}/{path.lstrip('/')}"


def _scheme() -> str:
    """Same scheme as Press itself: https in production, http in local browser tests, so
    a test paper reaches the test server the way a real paper reaches scroll.press."""
    return urlsplit(get_base_url()).scheme


def content_origin_pattern() -> str:
    """Pattern for CSP frame-src, or "" when there is no content domain."""
    domain = get_content_domain()
    return f"{_scheme()}://*.{domain}" if domain else ""


def _press_origin() -> bytes:
    parts = urlsplit(get_base_url())
    return f"{parts.scheme}://{parts.netloc}".encode()


async def _not_found(send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": b"Not found"})


class ContentDomainMiddleware:
    """Must be the outermost middleware, so every other layer sees the mapped path."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        host = dict(scope["headers"]).get(b"host", b"").decode("latin-1")
        url_hash = content_host_hash(host)
        if url_hash is None:
            return await self.app(scope, receive, send)
        if not url_hash or scope["method"] not in ("GET", "HEAD"):
            return await _not_found(send)

        path = f"/scroll/{url_hash}/paper/{scope['path'].lstrip('/')}"
        scope = dict(scope, path=path, raw_path=path.encode())
        replaced = False

        async def send_paper_only(message):
            nonlocal replaced
            if replaced:
                return
            if message["type"] == "http.response.start":
                # Error pages are Press pages with Press links, and redirects would point
                # at Press paths. Papers get a plain answer. 304 is a normal cache answer.
                status = message["status"]
                if status >= 400 or (300 <= status < 400 and status != 304):
                    replaced = True
                    return await _not_found(send)
                headers = []
                for name, value in message["headers"]:
                    if name.lower() in _DROPPED_HEADERS:
                        continue
                    if name.lower() == b"content-security-policy":
                        value = value.replace(
                            b"frame-ancestors 'self'", b"frame-ancestors " + _press_origin()
                        )
                    headers.append((name, value))
                message = dict(message, headers=headers)
            await send(message)

        await self.app(scope, receive, send_paper_only)
