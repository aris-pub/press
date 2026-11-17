"""Mark the math in an abstract for MathJax (prs-58a).

Abstracts are plain text that may hold TeX between $...$, $$...$$, \\(...\\) or \\[...\\].
abstract_html escapes the text and wraps each formula in <span class="math-tex"> as
\\(...\\) or \\[...\\]. MathJax (static/js/abstract-math.js) typesets only those spans,
so a dollar sign anywhere else on the page stays text.

A $...$ counts as math only when the opening $ is followed by a non-space, the closing $
is preceded by one, and no digit follows the closing $, so "between $5 and $10" is money.

*text* outside math becomes <em>text</em>. Authors write emphasis this way in plain-text
abstracts, and the stars used to show up as literal asterisks. A pair may hold math,
as in "*$k$-blocking operator*". A star with no partner stays a star.
"""

import html
import re

_MATH = re.compile(
    r"""
      (?P<escaped>\\\$)
    | \$\$(?P<display>.+?)\$\$
    | \\\[(?P<bracket>.+?)\\\]
    | \\\((?P<paren>.+?)\\\)
    | \$(?P<inline>[^\s$](?:[^$]*?[^\s$])?)\$(?!\d)
    """,
    re.DOTALL | re.VERBOSE,
)


def _text(raw: str, terms_pattern: re.Pattern | None) -> str:
    """Escape plain text, wrapping search terms in <mark>. Terms are matched on the raw
    text in one pass, so a term can never match inside a tag added for another."""
    if terms_pattern is None:
        return html.escape(raw)
    out = []
    position = 0
    for match in terms_pattern.finditer(raw):
        out.append(html.escape(raw[position : match.start()]))
        out.append(f"<mark>{html.escape(match.group(0))}</mark>")
        position = match.end()
    out.append(html.escape(raw[position:]))
    return "".join(out)


_OPEN_BEFORE = set(" \t\n([{\"'/-")
_CLOSE_AFTER = set(" \t\n)]}\"'/-.,;:!?")


def _emphasis_stars(text: str, math_spans: list[tuple[int, int]]) -> dict[int, str]:
    """Map the position of each paired emphasis star outside math to <em> or </em>."""

    def in_math(i: int) -> bool:
        return any(start <= i < end for start, end in math_spans)

    tags: dict[int, str] = {}
    opened = None
    for i, ch in enumerate(text):
        if ch != "*" or in_math(i):
            continue
        before = text[i - 1] if i > 0 else " "
        after = text[i + 1] if i + 1 < len(text) else " "
        if "*" in (before, after):
            continue
        if opened is None:
            if before in _OPEN_BEFORE and not after.isspace():
                opened = i
        elif not before.isspace() and after in _CLOSE_AFTER:
            tags[opened], tags[i] = "<em>", "</em>"
            opened = None
    return tags


def _text_with_emphasis(
    text: str, start: int, end: int, tags: dict[int, str], terms_pattern
) -> str:
    out = []
    position = start
    for i in sorted(k for k in tags if start <= k < end):
        out.append(_text(text[position:i], terms_pattern))
        out.append(tags[i])
        position = i + 1
    out.append(_text(text[position:end], terms_pattern))
    return "".join(out)


def abstract_html(text: str | None, terms=()) -> str:
    """Safe HTML for an abstract: escaped, math marked for MathJax, search terms marked."""
    if not text:
        return ""
    words = sorted({t for t in terms if t}, key=len, reverse=True)
    terms_pattern = (
        re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE) if words else None
    )
    matches = list(_MATH.finditer(text))
    tags = _emphasis_stars(text, [(m.start(), m.end()) for m in matches if not m.group("escaped")])
    out = []
    position = 0
    for match in matches:
        out.append(_text_with_emphasis(text, position, match.start(), tags, terms_pattern))
        if match.group("escaped"):
            out.append("$")
        elif match.group("inline") is not None or match.group("paren") is not None:
            tex = (
                match.group("inline")
                if match.group("inline") is not None
                else match.group("paren")
            )
            out.append(f'<span class="math-tex">\\({html.escape(tex)}\\)</span>')
        else:
            tex = (
                match.group("display")
                if match.group("display") is not None
                else match.group("bracket")
            )
            out.append(f'<span class="math-tex math-display">\\[{html.escape(tex)}\\]</span>')
        position = match.end()
    out.append(_text_with_emphasis(text, position, len(text), tags, terms_pattern))
    return "".join(out)
