#!/usr/bin/env python3
"""make_brand_assets.py — render Leverage Mind brand graphics from BRAND_SPEC.md.

Produces transparent PNG overlays used by the video editor:
  - wordmark.png          : "LEVERAGE MIND" wordmark + gold rule (transparent)
  - lower_third.png       : "James Harrington | Leverage Mind" lower-third (transparent)
  - endcard_16x9.png      : full end card (navy bg, wordmark, tagline, CTA)
  - icon_lm.png           : "LM" monogram, gold on navy circle (avatar/favicon)

All colors/fonts come from brand/BRAND_SPEC.md (single source of truth).
Run: python3 brand/make_brand_assets.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
OUT = HERE / "assets"
OUT.mkdir(exist_ok=True)

# --- Brand palette (BRAND_SPEC.md §3) ---
NAVY = (27, 42, 74, 255)        # #1B2A4A
GOLD = (200, 151, 62, 255)      # #C8973E
IVORY = (245, 240, 232, 255)    # #F5F0E8
CHARCOAL = (45, 45, 45, 255)    # #2D2D2D
OXBLOOD = (107, 29, 42, 255)    # #6B1D2A
TRANSPARENT = (0, 0, 0, 0)

PLAYFAIR = str(FONTS / "PlayfairDisplay.ttf")
INTER = str(FONTS / "Inter.ttf")


def font(path, size, weight=None):
    f = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def text_w(draw, s, fnt, tracking=0):
    w = draw.textlength(s, font=fnt)
    if tracking:
        w += tracking * max(len(s) - 1, 0)
    return w


def draw_tracked(draw, xy, s, fnt, fill, tracking=0, anchor_center_x=None):
    """Draw text with letter tracking. If anchor_center_x given, center on it."""
    total = text_w(draw, s, fnt, tracking)
    x, y = xy
    if anchor_center_x is not None:
        x = anchor_center_x - total / 2
    for ch in s:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


def make_wordmark():
    """Transparent wordmark: LEVERAGE MIND in Playfair Bold navy + gold rule."""
    W, H = 1200, 320
    img = Image.new("RGBA", (W, H), TRANSPARENT)
    d = ImageDraw.Draw(img)
    f = font(PLAYFAIR, 110, weight=700)
    word = "LEVERAGE MIND"
    tracking = 6
    total = text_w(d, word, f, tracking)
    cx = W / 2
    draw_tracked(d, (0, 70), word, f, NAVY, tracking, anchor_center_x=cx)
    # gold rule beneath
    rule_w = total * 0.92
    ry = 215
    d.rectangle([cx - rule_w / 2, ry, cx + rule_w / 2, ry + 7], fill=GOLD)
    img.save(OUT / "wordmark.png")
    # white variant for dark backgrounds
    img2 = Image.new("RGBA", (W, H), TRANSPARENT)
    d2 = ImageDraw.Draw(img2)
    draw_tracked(d2, (0, 70), word, f, IVORY, tracking, anchor_center_x=cx)
    d2.rectangle([cx - rule_w / 2, ry, cx + rule_w / 2, ry + 7], fill=GOLD)
    img2.save(OUT / "wordmark_ivory.png")
    print("wordmark.png, wordmark_ivory.png")


def make_lower_third():
    """Transparent lower-third bar: name + brand, Inter Medium."""
    W, H = 900, 150
    img = Image.new("RGBA", (W, H), TRANSPARENT)
    d = ImageDraw.Draw(img)
    # subtle translucent navy pill
    pill = Image.new("RGBA", (W, H), TRANSPARENT)
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle([0, 30, 760, 130], radius=12, fill=(27, 42, 74, 210))
    img = Image.alpha_composite(img, pill)
    d = ImageDraw.Draw(img)
    # gold accent bar at left
    d.rectangle([0, 30, 10, 130], fill=GOLD)
    name_f = font(INTER, 42, weight=600)
    brand_f = font(INTER, 28, weight=500)
    d.text((40, 48), "James Harrington", font=name_f, fill=IVORY)
    d.text((42, 96), "LEVERAGE MIND", font=brand_f, fill=GOLD)
    img.save(OUT / "lower_third.png")
    print("lower_third.png")


def make_endcard():
    """Full 1920x1080 end card: navy bg, wordmark, tagline, CTA."""
    W, H = 1920, 1080
    img = Image.new("RGBA", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    cx = W / 2
    # wordmark
    wf = font(PLAYFAIR, 130, weight=700)
    draw_tracked(d, (0, 360), "LEVERAGE MIND", wf, IVORY, tracking=8, anchor_center_x=cx)
    # gold rule
    rule_w = 760
    d.rectangle([cx - rule_w / 2, 530, cx + rule_w / 2, 538], fill=GOLD)
    # tagline (Playfair italic-ish regular, gold)
    tf = font(PLAYFAIR, 52, weight=500)
    draw_tracked(d, (0, 580), "The unfair advantage is a system.", tf, GOLD,
                 tracking=2, anchor_center_x=cx)
    # CTA (Inter)
    cf = font(INTER, 40, weight=500)
    draw_tracked(d, (0, 760), "SUBSCRIBE  \u00b7  leveragemind.consulting", cf, IVORY,
                 tracking=3, anchor_center_x=cx)
    img.convert("RGB").save(OUT / "endcard_16x9.png")
    print("endcard_16x9.png")


def make_icon():
    """LM monogram, gold on navy circle."""
    S = 512
    img = Image.new("RGBA", (S, S), TRANSPARENT)
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, S, S], fill=NAVY)
    f = font(PLAYFAIR, 250, weight=700)
    s = "LM"
    w = d.textlength(s, font=f)
    bbox = d.textbbox((0, 0), s, font=f)
    h = bbox[3] - bbox[1]
    d.text(((S - w) / 2, (S - h) / 2 - bbox[1]), s, font=f, fill=GOLD)
    img.save(OUT / "icon_lm.png")
    print("icon_lm.png")


if __name__ == "__main__":
    make_wordmark()
    make_lower_third()
    make_endcard()
    make_icon()
    print(f"\nAll assets written to {OUT}")
