#!/usr/bin/env python3
"""render_graphics.py — Deterministic graphics overlay renderer (TKT-11).

Renders branded RGBA PNG overlays at 1920x1080 for compositing onto video.
Layouts: lower_third, key_line, stat_callout, side_by_side.

Usage:
  python3 scripts/render_graphics.py --spec '{"layout":"lower_third","text":"HELLO"}' --output out.png
  python3 scripts/render_graphics.py --batch media_plan.json --project-dir <dir>
"""
import argparse
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Brand palette
NAVY = (27, 42, 74)       # #1B2A4A
GOLD = (200, 151, 62)     # #C8973E
IVORY = (245, 240, 232)   # #F5F0E8

W, H = 1920, 1080
MARGIN_X = int(W * 0.10)
MARGIN_Y = int(H * 0.10)
SAFE_W = W - 2 * MARGIN_X
SAFE_H = H - 2 * MARGIN_Y


def _font(size, bold=False):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap(text, font, max_width, draw):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines or [""]


def render_lower_third(spec):
    """Name/citation strip in lower-third zone."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = spec.get("text", "")
    subtitle = spec.get("subtitle", "")
    band_h = 100
    y0 = H - MARGIN_Y - band_h
    d.rectangle([MARGIN_X, y0, W - MARGIN_X, y0 + band_h], fill=(*NAVY, 220))
    d.rectangle([MARGIN_X, y0, MARGIN_X + 8, y0 + band_h], fill=(*GOLD, 255))
    f_main = _font(36, bold=True)
    lines = _wrap(text, f_main, SAFE_W - 40, d)
    d.text((MARGIN_X + 24, y0 + 14), lines[0], font=f_main, fill=(*IVORY, 255))
    if subtitle:
        f_sub = _font(24)
        d.text((MARGIN_X + 24, y0 + 58), subtitle[:80], font=f_sub, fill=(*GOLD, 255))
    return img


def render_key_line(spec):
    """Large centered quote/payoff line on scrim."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = spec.get("text", "")
    f = _font(52, bold=True)
    lines = _wrap(text, f, SAFE_W - 80, d)
    line_h = 68
    block_h = line_h * len(lines)
    cy = H // 2
    y0 = cy - block_h // 2 - 30
    y1 = cy + block_h // 2 + 30
    d.rectangle([MARGIN_X, y0, W - MARGIN_X, y1], fill=(30, 30, 30, 180))
    d.rectangle([MARGIN_X + 40, y0 + 8, W - MARGIN_X - 40, y0 + 12], fill=(*GOLD, 255))
    y = cy - block_h // 2
    for i, ln in enumerate(lines):
        bbox = d.textbbox((0, 0), ln, font=f)
        lw = bbox[2] - bbox[0]
        color = GOLD if i == len(lines) - 1 else IVORY
        d.text((W // 2 - lw // 2, y), ln, font=f, fill=(*color, 255))
        y += line_h
    return img


def render_stat_callout(spec):
    """Large statistic with label, centered."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stat = spec.get("stat", spec.get("text", ""))
    label = spec.get("label", "")
    f_stat = _font(120, bold=True)
    f_label = _font(32)
    bbox = d.textbbox((0, 0), stat, font=f_stat)
    sw = bbox[2] - bbox[0]
    sh = bbox[3] - bbox[1]
    sx = W // 2 - sw // 2
    sy = H // 2 - sh // 2 - 30
    pad = 50
    d.rectangle([sx - pad, sy - pad, sx + sw + pad, sy + sh + 80], fill=(30, 30, 30, 180))
    d.text((sx, sy), stat, font=f_stat, fill=(*GOLD, 255))
    if label:
        lbbox = d.textbbox((0, 0), label, font=f_label)
        lw = lbbox[2] - lbbox[0]
        d.text((W // 2 - lw // 2, sy + sh + 20), label, font=f_label, fill=(*IVORY, 255))
    return img


def render_side_by_side(spec):
    """Two-column comparison layout."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    left_title = spec.get("left_title", "A")
    right_title = spec.get("right_title", "B")
    left_items = spec.get("left_items", [spec.get("left_text", "")])
    right_items = spec.get("right_items", [spec.get("right_text", "")])
    mid = W // 2
    f_title = _font(36, bold=True)
    f_item = _font(28)
    # Panels
    d.rectangle([MARGIN_X, MARGIN_Y, mid - 20, H - MARGIN_Y], fill=(30, 30, 30, 160))
    d.rectangle([mid + 20, MARGIN_Y, W - MARGIN_X, H - MARGIN_Y], fill=(30, 30, 30, 160))
    # Titles
    d.text((MARGIN_X + 20, MARGIN_Y + 20), left_title, font=f_title, fill=(*GOLD, 255))
    d.text((mid + 40, MARGIN_Y + 20), right_title, font=f_title, fill=(*GOLD, 255))
    # Items
    col_w = mid - MARGIN_X - 60
    y = MARGIN_Y + 80
    for item in left_items[:10]:
        lines = _wrap(str(item), f_item, col_w, d)
        for ln in lines:
            if y > H - MARGIN_Y - 40:
                break
            d.text((MARGIN_X + 20, y), ln, font=f_item, fill=(*IVORY, 255))
            y += 38
    y = MARGIN_Y + 80
    for item in right_items[:10]:
        lines = _wrap(str(item), f_item, col_w, d)
        for ln in lines:
            if y > H - MARGIN_Y - 40:
                break
            d.text((mid + 40, y), ln, font=f_item, fill=(*IVORY, 255))
            y += 38
    return img


RENDERERS = {
    "lower_third": render_lower_third,
    "key_line": render_key_line,
    "stat_callout": render_stat_callout,
    "side_by_side": render_side_by_side,
}


def render_spec(spec, output_path):
    """Render a single overlay spec to a PNG. Raises RuntimeError on unknown layout."""
    layout = spec.get("layout")
    if layout not in RENDERERS:
        raise RuntimeError(
            f"Unknown graphics layout '{layout}'. "
            f"Supported: {', '.join(sorted(RENDERERS.keys()))}")
    img = RENDERERS[layout](spec)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    return output_path


def render_batch(media_plan_path, project_dir):
    """Render all beats with graphic.required=true from a media plan."""
    plan = json.loads(Path(media_plan_path).read_text())
    out_dir = Path(project_dir) / "assets" / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for beat in plan.get("beats", []):
        # Canonical field is 'graphics' (list); fall back to 'graphic' (singular dict).
        graphics_list = beat.get("graphics") or []
        if not graphics_list and beat.get("graphic"):
            graphics_list = [beat.get("graphic")]
        beat_id = beat.get("beat_id", beat.get("id", "unknown"))
        for gi, graphic in enumerate(graphics_list):
            if not graphic.get("required"):
                continue
            spec = {**graphic}
            spec.setdefault("layout", graphic.get("layout", graphic.get("type")))
            suffix = f"_{gi}" if len(graphics_list) > 1 else ""
            out_path = out_dir / f"{beat_id}{suffix}_overlay.png"
            render_spec(spec, out_path)
            rendered.append(str(out_path))
            print(f"  ✓ {beat_id} [{spec.get('layout')}] → {out_path.name}")
    print(f"  Rendered {len(rendered)} overlay(s)")
    return rendered


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render graphics overlay PNGs.")
    ap.add_argument("--spec", help="JSON spec string for single render")
    ap.add_argument("--output", help="Output path (single mode)")
    ap.add_argument("--batch", help="Path to media_plan.json (batch mode)")
    ap.add_argument("--project-dir", help="Project directory (batch mode)")
    args = ap.parse_args(argv)

    if args.spec:
        if not args.output:
            ap.error("--output required with --spec")
        spec = json.loads(args.spec)
        render_spec(spec, args.output)
        print(f"  ✓ rendered → {args.output}")
        return 0
    elif args.batch:
        if not args.project_dir:
            ap.error("--project-dir required with --batch")
        render_batch(args.batch, args.project_dir)
        return 0
    else:
        ap.error("Provide --spec or --batch")


if __name__ == "__main__":
    raise SystemExit(main())
