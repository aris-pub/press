"""OpenGraph image generator for scroll social previews.

Generates branded 1200x630 PNG images with title, authors, subject,
and abstract excerpt for rich link previews on social platforms.
"""

import io

from PIL import Image, ImageDraw, ImageFont

OG_WIDTH = 1200
OG_HEIGHT = 630

BG_COLOR = (255, 255, 255)
HEADER_BG = (185, 28, 28)
HEADER_TEXT = (255, 255, 255)
TEXT_COLOR = (34, 34, 34)
SUBTLE_COLOR = (100, 100, 100)
DIVIDER_COLOR = (210, 210, 210)
FOOTER_BG = (245, 245, 245)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    """Wrap text using actual font measurements."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font,
    color: tuple,
    max_lines: int = 99,
    line_spacing: int = 8,
) -> int:
    """Draw wrapped text using actual font metrics. Returns y after last line."""
    lines = _wrap_text(text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while font.getbbox(last + "...")[2] > max_width and len(last) > 10:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-4]
        lines[-1] = last + "..."

    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        bbox = font.getbbox(line)
        y += (bbox[3] - bbox[1]) + line_spacing
    return y


def generate_og_image(title: str, authors: str, subject: str, abstract: str = "") -> bytes:
    """Generate a 1200x630 OG image with scroll metadata."""
    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    px = 60
    content_w = OG_WIDTH - px * 2

    # Red header bar with subject
    header_h = 56
    draw.rectangle([0, 0, OG_WIDTH, header_h], fill=HEADER_BG)
    font_subject = _get_font(22, bold=True)
    draw.text((px, 16), subject.upper(), font=font_subject, fill=HEADER_TEXT)

    # Title
    y = header_h + 30
    font_title = _get_font(52, bold=True)
    y = _draw_wrapped(
        draw, title, px, y, content_w, font_title, TEXT_COLOR, max_lines=2, line_spacing=6
    )

    # Authors
    y += 10
    font_authors = _get_font(28)
    y = _draw_wrapped(draw, authors, px, y, content_w, font_authors, SUBTLE_COLOR, max_lines=1)

    # Divider
    y += 16
    draw.line([(px, y), (px + content_w, y)], fill=DIVIDER_COLOR, width=2)
    y += 16

    # Abstract — fill remaining space above footer
    if abstract:
        footer_h = 56
        available_h = OG_HEIGHT - footer_h - y - 20
        clean = " ".join(abstract.replace("\r\n", " ").replace("\n", " ").split())
        font_abs = _get_font(24)
        line_h = font_abs.getbbox("Ag")[3] + 8
        max_abs_lines = max(2, available_h // line_h)
        _draw_wrapped(
            draw,
            clean,
            px,
            y,
            content_w,
            font_abs,
            SUBTLE_COLOR,
            max_lines=max_abs_lines,
            line_spacing=8,
        )

    # Footer
    footer_y = OG_HEIGHT - 56
    draw.rectangle([0, footer_y, OG_WIDTH, OG_HEIGHT], fill=FOOTER_BG)
    draw.line([(0, footer_y), (OG_WIDTH, footer_y)], fill=DIVIDER_COLOR, width=1)
    font_brand = _get_font(24, bold=True)
    draw.text((px, footer_y + 16), "Scroll Press", font=font_brand, fill=TEXT_COLOR)
    font_tag = _get_font(20)
    brand_w = font_brand.getbbox("Scroll Press")[2]
    draw.text(
        (px + brand_w + 20, footer_y + 18),
        "HTML-native preprint server",
        font=font_tag,
        fill=SUBTLE_COLOR,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
