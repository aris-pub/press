"""The bridge script Press adds to every paper HTML response (prs-2m6, step 3).

The script goes in before any author markup, so it runs before the author's scripts.
Everything else in the author's bytes stays exactly as uploaded.
"""

import pytest

from app.paper_bridge import BRIDGE_SCRIPT, BRIDGE_VERSION, SCAN_LIMIT, inject_bridge, paper_etag

TAG = BRIDGE_SCRIPT


def _strip(out: bytes) -> bytes:
    assert out.count(TAG) == 1
    return out.replace(TAG, b"", 1)


@pytest.mark.parametrize(
    "html, before",
    [
        (b"<!DOCTYPE html><html><head><title>T</title></head></html>", b"<head>"),
        (b"<html><HEAD lang='en'><title>T</title></HEAD></html>", b"<HEAD lang='en'>"),
        (b"<!doctype html>\n<html lang=en>\n<body>x</body></html>", b"<html lang=en>"),
        (b"<!DOCTYPE html>\n<p>no html or head tag</p>", b"<!DOCTYPE html>"),
    ],
)
def test_script_goes_right_after_the_first_head_html_or_doctype_tag(html, before):
    out = inject_bridge(html)
    assert out.index(TAG) == out.index(before) + len(before)
    assert _strip(out) == html


def test_header_element_is_not_mistaken_for_head():
    html = b"<html><body><header>top</header></body></html>"
    out = inject_bridge(html)
    assert out.index(TAG) == len(b"<html>")


def test_fragment_without_any_tag_gets_the_script_first():
    html = b"<h1>Inline</h1>"
    assert inject_bridge(html) == TAG + html


def test_byte_order_mark_stays_first():
    html = b"\xef\xbb\xbf<h1>x</h1>"
    out = inject_bridge(html)
    assert out.startswith(b"\xef\xbb\xbf" + TAG)
    assert _strip(out) == html


def test_head_beyond_the_scan_limit_is_not_searched_for():
    html = b"<!DOCTYPE html>" + b"<!--" + b"x" * SCAN_LIMIT + b"--><head></head>"
    out = inject_bridge(html)
    assert out.index(TAG) == len(b"<!DOCTYPE html>")


def test_bytes_that_are_not_utf8_pass_through_unchanged():
    html = b"<html><head><meta charset=latin1></head><body>caf\xe9</body></html>"
    assert _strip(inject_bridge(html)) == html


def test_str_input_is_accepted():
    assert inject_bridge("<head></head>") == b"<head>" + TAG + b"</head>"


def test_script_cannot_close_its_own_tag_early():
    body = BRIDGE_SCRIPT[BRIDGE_SCRIPT.index(b">") + 1 : -len(b"</script>")]
    assert b"</script" not in body.lower()


def test_etag_changes_with_the_bridge_version():
    assert paper_etag("abc") == f'"abc.{BRIDGE_VERSION}"'
    assert len(BRIDGE_VERSION) == 12
