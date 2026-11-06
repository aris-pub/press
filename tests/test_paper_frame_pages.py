"""Press pages never reach into the paper frame directly (prs-2m6, step 3).

Once the paper is sandboxed, contentDocument and the frame's window are out of reach, so
the scroll page and the preview page talk to the paper only through messages, using
static/js/paper-frame.js.
"""

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["app/templates/scroll.html", "app/templates/preview.html"]


@pytest.mark.parametrize("page", PAGES)
def test_page_does_not_reach_into_the_frame(page):
    text = (ROOT / page).read_text()
    assert "contentDocument" not in text
    assert "contentWindow" not in text


@pytest.mark.parametrize("page", PAGES)
def test_frame_is_loaded_by_the_shared_script(page):
    text = (ROOT / page).read_text()
    frame = re.search(r"<iframe[^>]*id=\"paper-frame\"[^>]*>", text, re.S).group(0)
    assert " src=" not in frame
    assert "data-src=" in frame
    assert "data-settings-key=" in frame
    assert re.search(r"<script[^>]*src=\"/static/js/paper-frame\.js\"[^>]*nonce=", text)


def test_shared_script_checks_who_sent_each_message():
    text = (ROOT / "static/js/paper-frame.js").read_text()
    assert "event.source !== iframe.contentWindow" in text
