"""OpenGraph image generator for scroll social previews.

Generates branded 1200x630 PNG images with title, authors, subject,
and abstract excerpt for rich link previews on social platforms.
"""

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont

OG_WIDTH = 1200
OG_HEIGHT = 630

# Brand colors
BG_COLOR = (250, 250, 250)
TEXT_COLOR = (34, 34, 34)
ACCENT_COLOR = (185, 28, 28)
SUBTLE_COLOR = (107, 114, 128)
DIVIDER_COLOR = (220, 220, 220)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font, falling back to default if system fonts aren't available."""
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


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    color: tuple,
    max_lines: int = 3,
    line_spacing: int = 6,
) -> int:
    """Draw wrapped text and return the y position after the last line."""
    avg_char_width = font.size * 0.55 if hasattr(font, "size") else 10
    chars_per_line = max(20, int(max_width / avg_char_width))

    lines = textwrap.wrap(text, width=chars_per_line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines[-1]:
            lines[-1] = lines[-1][:-3] + "..." if len(lines[-1]) > 3 else "..."

    line_height = (font.size if hasattr(font, "size") else 14) + line_spacing
    for line in lines:
        draw.text((x, y), line, font=font, fill=color)
        y += line_height

    return y


def generate_og_image(
    title: str, authors: str, subject: str, abstract: str = ""
) -> bytes:
    """Generate a 1200x630 OG image with scroll metadata.

    Returns PNG bytes.
    """
    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Accent bar at top
    draw.rectangle([0, 0, OG_WIDTH, 6], fill=ACCENT_COLOR)

    padding_x = 72
    content_width = OG_WIDTH - (padding_x * 2)

    # Subject label
    font_subject = _get_font(22)
    draw.text((padding_x, 36), subject.upper(), font=font_subject, fill=ACCENT_COLOR)

    # Title
    font_title = _get_font(48, bold=True)
    y = _draw_text_block(
        draw, title, padding_x, 70, content_width, font_title, TEXT_COLOR, max_lines=3
    )

    # Authors
    font_authors = _get_font(26)
    y = _draw_text_block(
        draw, authors, padding_x, y + 14, content_width, font_authors, SUBTLE_COLOR, max_lines=1
    )

    # Divider
    y += 12
    draw.line([(padding_x, y), (padding_x + content_width, y)], fill=DIVIDER_COLOR, width=1)

    # Abstract
    if abstract:
        clean_abstract = " ".join(abstract.replace("\r\n", " ").replace("\n", " ").split())
        font_abstract = _get_font(22)
        _draw_text_block(
            draw,
            clean_abstract,
            padding_x,
            y + 16,
            content_width,
            font_abstract,
            SUBTLE_COLOR,
            max_lines=6,
            line_spacing=5,
        )

    # Platform branding at bottom
    draw.rectangle([0, OG_HEIGHT - 56, OG_WIDTH, OG_HEIGHT], fill=(245, 245, 245))
    draw.line([(0, OG_HEIGHT - 56), (OG_WIDTH, OG_HEIGHT - 56)], fill=DIVIDER_COLOR, width=1)

    font_brand = _get_font(22, bold=True)
    draw.text((padding_x, OG_HEIGHT - 40), "Scroll Press", font=font_brand, fill=TEXT_COLOR)

    font_tagline = _get_font(17)
    draw.text(
        (padding_x + 160, OG_HEIGHT - 38),
        "HTML-native preprint server",
        font=font_tagline,
        fill=SUBTLE_COLOR,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
