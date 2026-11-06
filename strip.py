"""Turns captured photos into a classic photobooth strip.

Sizes are in inches x dpi, so the output prints at the right physical size:
  strip        2x6 in  (600 x 1800 px at 300 dpi)  -> one strip
  4x6_double   4x6 in  (1200 x 1800 px)            -> two identical strips side by side,
                                                       print on 4x6 photo paper and cut down the middle
"""
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_CANDIDATES = [
    # Raspberry Pi / Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # Mac
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def frame_to_pil(frame_bgr):
    """OpenCV gives BGR; Pillow wants RGB."""
    return Image.fromarray(frame_bgr[:, :, ::-1].copy())


def _fit_font(draw, text, max_width, start_size):
    size = start_size
    font = load_font(size)
    while size > 10 and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = load_font(size)
    return font


def compose_strip(photos, footer_text="PHOTOBOOTH", date_text="", dpi=300,
                  background="#FFFFFF", text_color="#111111", grayscale=False):
    """photos: list of PIL images (any size/aspect). Returns a 2x6 inch PIL image."""
    if not photos:
        raise ValueError("Need at least one photo")

    W, H = 2 * dpi, 6 * dpi
    margin = round(0.10 * dpi)      # outer border
    gap = round(0.067 * dpi)        # space between photos
    footer_h = round(0.75 * dpi)    # space for the text at the bottom

    n = len(photos)
    slot_w = W - 2 * margin
    slot_h = (H - margin - footer_h - gap * (n - 1)) // n
    if slot_h < 50:
        raise ValueError(f"Too many photos ({n}) for one strip")

    strip = Image.new("RGB", (W, H), background)
    for i, photo in enumerate(photos):
        # Center-crop each photo to fill its slot exactly (no stretching, no bars).
        fitted = ImageOps.fit(photo.convert("RGB"), (slot_w, slot_h), Image.LANCZOS)
        strip.paste(fitted, (margin, margin + i * (slot_h + gap)))

    # Footer text, centered in whatever space is left under the last photo.
    draw = ImageDraw.Draw(strip)
    footer_top = margin + n * slot_h + (n - 1) * gap
    title_font = _fit_font(draw, footer_text, slot_w, round(0.20 * dpi))
    date_font = _fit_font(draw, date_text, slot_w, round(0.09 * dpi)) if date_text else None

    lines = [(footer_text, title_font)] + ([(date_text, date_font)] if date_text else [])
    line_gap = round(0.07 * dpi)
    heights = [draw.textbbox((0, 0), t, font=f)[3] - draw.textbbox((0, 0), t, font=f)[1]
               for t, f in lines]
    block_h = sum(heights) + line_gap * (len(lines) - 1)
    y = footer_top + (H - footer_top - block_h) // 2
    for (text, font), h in zip(lines, heights):
        top_offset = draw.textbbox((0, 0), text, font=font)[1]
        x = (W - draw.textlength(text, font=font)) / 2
        draw.text((x, y - top_offset), text, font=font, fill=text_color)
        y += h + line_gap

    if grayscale:
        strip = strip.convert("L").convert("RGB")
    return strip


def compose_sheet(strip, layout="strip", dpi=300):
    """Wrap the strip into what actually gets sent to the printer."""
    if layout == "strip":
        return strip
    if layout == "4x6_double":
        W, H = 4 * dpi, 6 * dpi
        sheet = Image.new("RGB", (W, H), "white")
        sheet.paste(strip, (0, 0))
        sheet.paste(strip, (W // 2, 0))
        # Small cut marks in the top/bottom margins only, so they never cross a photo.
        draw = ImageDraw.Draw(sheet)
        tick = round(0.06 * dpi)
        draw.line([(W // 2, 0), (W // 2, tick)], fill="#BBBBBB", width=2)
        draw.line([(W // 2, H - tick), (W // 2, H)], fill="#BBBBBB", width=2)
        return sheet
    raise ValueError(f"Unknown layout '{layout}' (use 'strip' or '4x6_double')")
