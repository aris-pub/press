"""OpenGraph image generator for scroll social previews.

Poster-style 1200x630 PNG: subject pill, large auto-fitting title, author line,
and the Scroll Press logomark + wordmark. No abstract or body text, which is
illegible at card size. Pure PIL; the logomark is a pre-rendered static asset.
"""

import io
import os
import re

from PIL import Image, ImageDraw, ImageFont

OG_WIDTH = 1200
OG_HEIGHT = 630

WHITE = (255, 255, 255)
CORAL = (255, 107, 107)      # #FF6B6B, Scroll Press product color (design-system.md)
TITLE_COLOR = (10, 10, 10)   # #0a0a0a
AUTHOR_COLOR = (122, 122, 122)  # #7a7a7a
SLATE = (60, 73, 82)         # #3C4952, wordmark
MARGIN = 80

_HERE = os.path.dirname(os.path.abspath(__file__))
LOGOMARK_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "static", "images", "press-logomark.png")
)

# Minimal LaTeX -> unicode so titles do not show raw $...$ source on the card.
_LATEX_MAP = {
    r"\\phi": "φ", r"\\alpha": "α", r"\\beta": "β", r"\\gamma": "γ",
    r"\\delta": "δ", r"\\epsilon": "ε", r"\\theta": "θ", r"\\lambda": "λ",
    r"\\mu": "μ", r"\\pi": "π", r"\\sigma": "σ", r"\\omega": "ω",
    r"\\Delta": "Δ", r"\\Sigma": "Σ", r"\\Omega": "Ω", r"\\times": "×",
    r"\\infty": "∞", r"\\to": "→", r"\\leq": "≤", r"\\geq": "≥",
}


def _clean(text: str) -> str:
    """Strip LaTeX math so titles do not render literal $...$ on the card."""
    if not text:
        return ""
    for pat, rep in _LATEX_MAP.items():
        text = re.sub(pat, rep, text)
    text = text.replace("$", "")
    text = re.sub(r"\\[a-zA-Z]+", "", text).replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def _sans(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _serif(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Times.ttc",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return _sans(size, bold=True)


def _wrap(text: str, font, max_width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if font.getbbox(test)[2] > max_width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _format_authors(authors: str) -> str:
    """One legible line: list up to three authors, else first author et al."""
    parts = [a.strip() for a in _clean(authors).split(",") if a.strip()]
    return ", ".join(parts) if len(parts) <= 3 else f"{parts[0]} et al."


def _fit_title(text: str, box_w: int, box_h: int, max_lines: int = 4):
    """Largest bold size whose wrapped title fits box_w x box_h in max_lines."""
    for size in (84, 76, 68, 60, 52, 46):
        font = _sans(size, bold=True)
        lines = _wrap(text, font, box_w)
        line_h = font.getbbox("Ag")[3] + 14
        if len(lines) <= max_lines and len(lines) * line_h <= box_h:
            return font, lines, line_h
    font = _sans(46, bold=True)
    lines = _wrap(text, font, box_w)
    line_h = font.getbbox("Ag")[3] + 14
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while font.getbbox(last + "…")[2] > box_w and len(last) > 8:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-2]
        lines[-1] = last + "…"
    return font, lines, line_h


def _pill(draw, right: int, yc: int, text: str, filled: bool) -> int:
    """Draw a pill with its right edge at `right`, centered on yc. Returns left x."""
    font = _sans(22, bold=True)
    tw = font.getbbox(text)[2]
    pad = 20
    pw = tw + pad * 2
    ph = font.getbbox("Ag")[3] + 22
    left = right - pw
    box = [left, yc - ph // 2, right, yc + ph // 2]
    if filled:
        draw.rounded_rectangle(box, radius=ph // 2, fill=CORAL)
        draw.text((left + pad, yc), text, font=font, fill=WHITE, anchor="lm")
    else:
        draw.rounded_rectangle(box, radius=ph // 2, outline=CORAL, width=3)
        draw.text((left + pad, yc), text, font=font, fill=CORAL, anchor="lm")
    return left


def generate_og_image(
    title: str, authors: str, subject: str, abstract: str = "", is_example: bool = False
) -> bytes:
    """Generate a 1200x630 OG card. `abstract` is accepted for compatibility but unused."""
    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)
    title = _clean(title)
    subject = _clean(subject)
    x = MARGIN

    # Title (hero), auto-fit near the top.
    font_title, lines, line_h = _fit_title(title, OG_WIDTH - MARGIN * 2, 340)
    y = 100
    for line in lines:
        draw.text((x, y), line, font=font_title, fill=TITLE_COLOR)
        y += line_h

    # Author line.
    y += 22
    draw.text((x, y), _format_authors(authors), font=_sans(30), fill=AUTHOR_COLOR)

    # Bottom band: logomark + "Scroll Press" wordmark on the left.
    yc = OG_HEIGHT - 76
    try:
        mark = Image.open(LOGOMARK_PATH).convert("RGBA")
        mark = mark.crop(mark.getbbox())
        mh = 46
        mw = int(mark.width * mh / mark.height)
        mark = mark.resize((mw, mh), Image.LANCZOS)
        img.paste(mark, (x, yc - mh // 2), mark)
        wordmark_x = x + mw + 16
    except (OSError, IOError):
        wordmark_x = x
    draw.text((wordmark_x, yc), "Scroll Press", font=_serif(34), fill=SLATE, anchor="lm")

    # Bottom band: subject (and example) pill on the right.
    right = OG_WIDTH - MARGIN
    if subject:
        right = _pill(draw, right, yc, subject.upper(), filled=True) - 16
    if is_example:
        _pill(draw, right, yc, "EXAMPLE", filled=False)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
