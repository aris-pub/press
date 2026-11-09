"""Mark the math in an abstract for MathJax (prs-58a).

Abstracts are plain text that may hold TeX between $...$, $$...$$, \\(...\\) or \\[...\\].
abstract_html escapes the text and wraps each formula in <span class="math-tex"> as
\\(...\\) or \\[...\\]. MathJax (static/js/abstract-math.js) typesets only those spans,
so a dollar sign anywhere else on the page stays text.

A $...$ counts as math only when the opening $ is followed by a non-space, the closing $
is preceded by one, and no digit follows the closing $, so "between $5 and $10" is money.
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


def abstract_html(text: str | None, terms=()) -> str:
    """Safe HTML for an abstract: escaped, math marked for MathJax, search terms marked."""
    if not text:
        return ""
    words = sorted({t for t in terms if t}, key=len, reverse=True)
    terms_pattern = (
        re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE) if words else None
    )
    out = []
    position = 0
    for match in _MATH.finditer(text):
        out.append(_text(text[position : match.start()], terms_pattern))
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
    out.append(_text(text[position:], terms_pattern))
    return "".join(out)
