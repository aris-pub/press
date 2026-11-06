"""Add Press's bridge script to paper HTML as it is served (prs-2m6, step 3).

The stored upload is never changed. The script is added on the way out, right after the
first <head>, <html> or doctype tag, so it runs before any author script.
"""

import hashlib
from pathlib import Path
import re

_SOURCE = (Path(__file__).parent.parent / "static/js/paper-bridge.js").read_bytes()

BRIDGE_SCRIPT = b"<script data-press-bridge>" + _SOURCE + b"</script>"
BRIDGE_VERSION = hashlib.sha256(_SOURCE).hexdigest()[:12]

# Only the start of the file is searched, so a huge paper costs nothing extra. A <head>
# further in than this is unusual enough that the script simply goes earlier.
SCAN_LIMIT = 64 * 1024

_BOM = b"\xef\xbb\xbf"
_ANCHORS = [
    re.compile(rb"<head(?:\s[^>]*)?>", re.IGNORECASE),
    re.compile(rb"<html(?:\s[^>]*)?>", re.IGNORECASE),
    re.compile(rb"<!doctype[^>]*>", re.IGNORECASE),
]


def inject_bridge(html: bytes | str) -> bytes:
    data = html.encode() if isinstance(html, str) else html
    window = data[:SCAN_LIMIT]
    for anchor in _ANCHORS:
        match = anchor.search(window)
        if match:
            return data[: match.end()] + BRIDGE_SCRIPT + data[match.end() :]
    start = len(_BOM) if data.startswith(_BOM) else 0
    return data[:start] + BRIDGE_SCRIPT + data[start:]


def paper_etag(content_hash: str) -> str:
    """The tag changes when the bridge does, so caches fetch the paper again."""
    return f'"{content_hash}.{BRIDGE_VERSION}"'
