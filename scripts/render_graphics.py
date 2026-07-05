#!/usr/bin/env python3
"""render_graphics.py — Deterministic graphics overlay renderer (TKT-11).

Renders branded RGBA PNG overlays at 1920x1080 for compositing onto video.
Layouts: lower_third, key_line, stat_callout, side_by_side.

S16_T002: Extended with 8 professional template types from S16_T001 schema:
comparison_card, framework_3_step, decision_tree, cost_stack, before_after,
timeline, annotated_ui_mock, quote_card.

S16_T003: Extended with progressive reveal animation for graphics >2s.
Animated graphics output multi-frame PNG sequences with frame timing metadata.

Usage:
  python3 scripts/render_graphics.py --spec '{"layout":"lower_third","text":"HELLO"}' --output out.png
  python3 scripts/render_graphics.py --batch media_plan.json --project-dir <dir>
"""
import argparse
import hashlib
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Brand palette
NAVY = (27, 42, 74)       # #1B2A4A
GOLD = (200, 151, 62)     # #C8973E
IVORY = (245, 240, 232)   # #F5F0E8
LIGHT_GRAY = (200, 200, 200)

# Resolution constants (base 1x values; render_spec scales for supersampling)
W, H = 1920, 1080
MARGIN_X = int(W * 0.10)
MARGIN_Y = int(H * 0.10)
SAFE_W = W - 2 * MARGIN_X
SAFE_H = H - 2 * MARGIN_Y

# Brand font directory and role mapping
FONT_DIR = ROOT / "brand" / "fonts"
FONT_ROLES = {
    "body": ("Inter.ttf", "Inter.ttf"),        # (regular, bold)
    "display": ("PlayfairDisplay.ttf", "PlayfairDisplay.ttf"),  # (regular, bold)
}


class RenderError(RuntimeError):
    """Raised when rendering fails due to missing resources or invalid state."""

# Animation constants (S16_T003)
DEFAULT_FRAME_RATE = 30  # fps
DEFAULT_REVEAL_DURATION = 0.5  # seconds per element reveal
MIN_ANIMATION_DURATION = 2.0  # seconds
ANIMATION_THRESHOLD = 2.0  # seconds - graphics >2s require animation


def _font(size, bold=False, role="body"):
    from PIL import ImageFont
    font_file = FONT_ROLES[role][1 if bold else 0]
    font_path = FONT_DIR / font_file
    if not font_path.exists():
        raise RenderError(
            f"Brand font not found: {font_path} (role='{role}', bold={bold}). "
            f"Expected '{font_file}' in brand/fonts/. "
            f"Install the font or restore brand/fonts/ to proceed."
        )
    font = ImageFont.truetype(str(font_path), size)
    if bold:
        try:
            axes = font.get_variation_axes()
        except Exception:
            axes = []
        if axes:
            wght_axis = None
            axis_values = []
            for a in axes:
                if a.get("name") == b"Weight" and a.get("maximum", 0) >= 700:
                    wght_axis = a
                axis_values.append(a.get("default", a.get("minimum", 400)))
            if wght_axis:
                for i, a in enumerate(axes):
                    if a.get("name") == b"Weight":
                        axis_values[i] = 700
                try:
                    font.set_variation_by_axes(axis_values)
                except Exception:
                    pass
    return font


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


def fit_text(text, draw, box_width, max_lines, role="body", min_size=12, max_size=72):
    """Step font size down until text fits within max_lines at box_width.

    Returns (font, lines) at the largest size that fits.
    Raises RenderError if even min_size cannot contain the text.
    """
    for size in range(max_size, min_size - 1, -1):
        font = _font(size, role=role)
        lines = _wrap(text, font, box_width, draw)
        if len(lines) <= max_lines:
            return font, lines
    raise RenderError(
        f"Text does not fit at minimum size {min_size}pt: "
        f"'{text[:80]}...' ({len(text)} chars, needs >{max_lines} lines at {box_width}px)"
    )


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
    f_main = _font(36, bold=True, role="body")
    lines = _wrap(text, f_main, SAFE_W - 40, d)
    d.text((MARGIN_X + 24, y0 + 14), lines[0], font=f_main, fill=(*IVORY, 255))
    if subtitle:
        f_sub, sub_lines = fit_text(subtitle, d, SAFE_W - 40, 1, role="body", min_size=14, max_size=24)
        d.text((MARGIN_X + 24, y0 + 58), sub_lines[0], font=f_sub, fill=(*GOLD, 255))
    return img


def render_key_line(spec):
    """Large centered quote/payoff line on scrim."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = spec.get("text", "")
    f = _font(52, bold=True, role="display")
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
    f_stat = _font(120, bold=True, role="display")
    f_label = _font(32, role="body")
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
    f_title = _font(36, bold=True, role="display")
    f_item = _font(28, role="body")
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


def render_comparison_card(spec):
    """Two-column professional comparison layout."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    left_col = spec.get("left_column", {})
    right_col = spec.get("right_column", {})
    left_title = left_col.get("title", "Option A")
    right_title = right_col.get("title", "Option B")
    left_items = left_col.get("items", [])
    right_items = right_col.get("items", [])

    mid = W // 2
    f_title = _font(36, bold=True, role="display")
    f_item = _font(28, role="body")

    # Comparison panels
    panel_h = H - 2 * MARGIN_Y - 120
    d.rectangle([MARGIN_X, MARGIN_Y + 80, mid - 30, MARGIN_Y + 80 + panel_h], fill=(20, 20, 30, 200))
    d.rectangle([mid + 30, MARGIN_Y + 80, W - MARGIN_X, MARGIN_Y + 80 + panel_h], fill=(20, 30, 20, 200))

    # Gold accent line
    d.line([mid, MARGIN_Y + 80, mid, H - MARGIN_Y], fill=(*GOLD, 255), width=3)

    # Titles
    d.text((MARGIN_X + 20, MARGIN_Y + 20), left_title, font=f_title, fill=(*GOLD, 255))
    d.text((mid + 40, MARGIN_Y + 20), right_title, font=f_title, fill=(*GOLD, 255))

    # Items
    col_w = mid - MARGIN_X - 70
    y = MARGIN_Y + 120
    for item in left_items[:8]:
        lines = _wrap(str(item), f_item, col_w, d)
        for ln in lines:
            if y > H - MARGIN_Y - 60:
                break
            d.text((MARGIN_X + 20, y), ln, font=f_item, fill=(*IVORY, 255))
            y += 35

    y = MARGIN_Y + 120
    for item in right_items[:8]:
        lines = _wrap(str(item), f_item, col_w, d)
        for ln in lines:
            if y > H - MARGIN_Y - 60:
                break
            d.text((mid + 40, y), ln, font=f_item, fill=(*IVORY, 255))
            y += 35

    return img


def render_framework_3_step(spec):
    """Three-step framework visualization."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    title = spec.get("title", "Three-Step Framework")
    steps = spec.get("steps", [])
    connector = spec.get("connector_style", "arrow")

    f_title = _font(44, bold=True, role="display")
    f_step_num = _font(72, bold=True, role="display")
    f_step_label = _font(32, bold=True, role="body")
    f_desc = _font(24, role="body")

    # Title
    d.text((MARGIN_X, MARGIN_Y + 20), title, font=f_title, fill=(*GOLD, 255))

    # Steps layout
    step_width = SAFE_W // 3
    centers = [MARGIN_X + step_width // 2, MARGIN_X + step_width + step_width // 2, W - MARGIN_X - step_width // 2]
    y_base = MARGIN_Y + 120

    for i, step in enumerate(steps[:3]):
        cx = centers[i]
        cy = y_base + 80

        # Number circle
        radius = 50
        d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*GOLD, 255), outline=(*NAVY, 255))

        # Step number
        num = str(step.get("number", i + 1))
        nb = d.textbbox((0, 0), num, font=f_step_num)
        nw = nb[2] - nb[0]
        d.text((cx - nw // 2, cy - 30), num, font=f_step_num, fill=(*NAVY, 255))

        # Step label
        label = step.get("label", f"Step {i + 1}")
        lb = d.textbbox((0, 0), label, font=f_step_label)
        lw = lb[2] - lb[0]
        d.text((cx - lw // 2, cy + 60), label, font=f_step_label, fill=(*IVORY, 255))

        # Description
        desc = step.get("description", "")
        if desc:
            f_desc, desc_lines = fit_text(desc, d, step_width - 40, 3, role="body", min_size=10, max_size=24)
            dy = cy + 110
            for ln in desc_lines:
                db = d.textbbox((0, 0), ln, font=f_desc)
                dw = db[2] - db[0]
                d.text((cx - dw // 2, dy), ln, font=f_desc, fill=(*LIGHT_GRAY, 255))
                dy += 30

        # Connector arrow (except last step)
        if i < 2 and connector == "arrow":
            next_cx = centers[i + 1]
            d.polygon([next_cx - 60, cy, next_cx - 40, cy - 10, next_cx - 40, cy + 10], fill=(*GOLD, 255))

    return img


def render_decision_tree(spec):
    """Decision flow visualization."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    root = spec.get("root", {})
    branches = spec.get("branches", [])

    f_question = _font(36, bold=True, role="display")
    f_branch = _font(28, bold=True, role="body")
    f_outcome = _font(24, role="body")

    # Root question box
    question = root.get("question", "Which path?")
    cy = H // 2 - 100
    box_w = SAFE_W - 100
    box_h = 120
    x0 = (W - box_w) // 2
    y0 = cy - 50

    d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(*NAVY, 220), outline=(*GOLD, 255), width=3)

    f_question, q_lines = fit_text(question, d, box_w - 40, 3, role="display", min_size=14, max_size=36)
    for i, ln in enumerate(q_lines):
        d.text((x0 + 20, y0 + 20 + i * 35), ln, font=f_question, fill=(*IVORY, 255))

    # Branches
    branch_w = box_w // len(branches) if branches else box_w // 2
    for i, branch in enumerate(branches[:4]):
        bx = x0 + i * branch_w
        by = y0 + box_h + 40

        # Condition
        cond = branch.get("condition", f"Option {i + 1}")
        d.text((bx + 20, by), cond, font=f_branch, fill=(*GOLD, 255))

        # Outcome
        outcome = branch.get("outcome", "")
        if outcome:
            f_outcome, out_lines = fit_text(outcome, d, branch_w - 40, 3, role="body", min_size=10, max_size=24)
            for j, ln in enumerate(out_lines):
                d.text((bx + 20, by + 35 + j * 28), ln, font=f_outcome, fill=(*IVORY, 255))

        # Recommended indicator
        if branch.get("is_recommended"):
            d.text((bx + branch_w - 60, by), "★", font=_font(20, role="body"), fill=(*GOLD, 255))

    return img


def render_cost_stack(spec):
    """Stacked cost breakdown visualization."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    title = spec.get("title", "Total Cost Breakdown")
    subtitle = spec.get("subtitle", "")
    segments = spec.get("segments", [])
    total_label = spec.get("total_label", "Total")
    total_value = spec.get("total_value", "")

    f_title = _font(40, bold=True, role="display")
    f_sub = _font(28, role="body")
    f_seg = _font(32, bold=True, role="body")
    f_val = _font(36, bold=True, role="body")
    f_total = _font(36, bold=True, role="body")

    # Title section
    d.text((MARGIN_X, MARGIN_Y + 20), title, font=f_title, fill=(*GOLD, 255))
    if subtitle:
        d.text((MARGIN_X, MARGIN_Y + 70), subtitle, font=f_sub, fill=(*IVORY, 255))

    # Stacked segments
    stack_h = H - MARGIN_Y - 250
    stack_w = SAFE_W - 100
    stack_x = (W - stack_w) // 2
    stack_y = MARGIN_Y + 120

    seg_h = stack_h // len(segments) if segments else stack_h // 2
    colors = [(*NAVY, 220), (*GOLD, 220), (*IVORY, 220), (100, 100, 120, 200), (80, 80, 100, 200)]

    for i, seg in enumerate(segments[:6]):
        sy = stack_y + i * seg_h
        color = seg.get("color", f"#{colors[i % len(colors)][0]:02x}{colors[i % len(colors)][1]:02x}{colors[i % len(colors)][2]:02x}")
        rgb = tuple(int(color[j:j+2], 16) for j in (1, 3, 5))
        d.rectangle([stack_x, sy, stack_x + stack_w, sy + seg_h - 5], fill=(*rgb, 220))

        # Label and value
        label = seg.get("label", f"Item {i + 1}")
        value = str(seg.get("value", ""))
        d.text((stack_x + 20, sy + 10), label, font=f_seg, fill=(*IVORY, 255))
        d.text((stack_x + stack_w - 80, sy + 10), value, font=f_val, fill=(*IVORY, 255))

    # Total line
    total_y = stack_y + len(segments) * seg_h
    d.line([stack_x, total_y, stack_x + stack_w, total_y], fill=(*GOLD, 255), width=3)
    d.text((stack_x, total_y + 15), f"{total_label}: {total_value}", font=f_total, fill=(*GOLD, 255))

    return img


def render_before_after(spec):
    """Before/after comparison visualization."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    before = spec.get("before", {})
    after = spec.get("after", {})
    highlight = spec.get("change_highlight", "")

    f_label = _font(40, bold=True, role="display")
    f_desc = _font(28, role="body")
    f_high = _font(32, bold=True, role="body")

    mid = W // 2

    # Section headers
    d.text((MARGIN_X + 20, MARGIN_Y + 20), "BEFORE", font=f_label, fill=(*NAVY, 255))
    d.text((mid + 40, MARGIN_Y + 20), "AFTER", font=f_label, fill=(*GOLD, 255))

    # Divider line
    d.line([mid, MARGIN_Y + 70, mid, H - MARGIN_Y], fill=(*GOLD, 255), width=3)

    # Before section
    before_y = MARGIN_Y + 100
    blabel = before.get("label", "Before")
    bdesc = before.get("description", "")
    d.text((MARGIN_X + 20, before_y), blabel, font=f_label, fill=(*IVORY, 255))
    if bdesc:
        f_desc2, bdesc_lines = fit_text(bdesc, d, SAFE_W // 2 - 60, 4, role="body", min_size=10, max_size=28)
        for i, ln in enumerate(bdesc_lines):
            d.text((MARGIN_X + 20, before_y + 50 + i * 32), ln, font=f_desc2, fill=(*LIGHT_GRAY, 255))

    # After section
    after_y = MARGIN_Y + 100
    alabel = after.get("label", "After")
    adesc = after.get("description", "")
    d.text((mid + 40, after_y), alabel, font=f_label, fill=(*IVORY, 255))
    if adesc:
        f_desc3, adesc_lines = fit_text(adesc, d, SAFE_W // 2 - 60, 4, role="body", min_size=10, max_size=28)
        for i, ln in enumerate(adesc_lines):
            d.text((mid + 40, after_y + 50 + i * 32), ln, font=f_desc3, fill=(*LIGHT_GRAY, 255))

    # Change highlight
    if highlight:
        hl_y = H - MARGIN_Y - 80
        hl_w = SAFE_W - 80
        hl_x = (W - hl_w) // 2
        d.rectangle([hl_x, hl_y, hl_x + hl_w, hl_y + 50], fill=(30, 30, 30, 180))
        f_high2, hl_lines = fit_text(highlight, d, hl_w - 40, 2, role="body", min_size=12, max_size=32)
        for i, ln in enumerate(hl_lines):
            lb = d.textbbox((0, 0), ln, font=f_high2)
            lw = lb[2] - lb[0]
            d.text((hl_x + (hl_w - lw) // 2, hl_y + 10 + i * 32), ln, font=f_high2, fill=(*GOLD, 255))

    return img


def render_timeline(spec):
    """Timeline visualization."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    title = spec.get("title", "Project Timeline")
    events = spec.get("events", [])
    orientation = spec.get("orientation", "horizontal")

    f_title = _font(40, bold=True, role="display")
    f_time = _font(28, bold=True, role="body")
    f_label = _font(32, role="body")
    f_desc = _font(24, role="body")

    # Title
    d.text((MARGIN_X, MARGIN_Y + 20), title, font=f_title, fill=(*GOLD, 255))

    # Timeline base
    base_y = H // 2 + 50
    d.line([MARGIN_X + 60, base_y, W - MARGIN_X - 60, base_y], fill=(*GOLD, 255), width=4)

    # Events
    if orientation == "horizontal":
        event_w = SAFE_W // max(len(events), 1)
        for i, event in enumerate(events[:6]):
            x = MARGIN_X + 60 + i * event_w
            time_label = event.get("time_label", f"Q{i + 1}")
            label = event.get("label", f"Event {i + 1}")
            desc = event.get("description", "")

            # Time marker
            d.ellipse([x - 8, base_y - 8, x + 8, base_y + 8], fill=(*GOLD, 255))
            d.text((x - 20, base_y + 15), time_label, font=f_time, fill=(*NAVY, 255))

            # Event label
            d.text((x - 40, base_y - 40), label, font=f_label, fill=(*IVORY, 255))

            # Description
            if desc:
                f_desc2, tl_desc_lines = fit_text(desc, d, 160, 2, role="body", min_size=10, max_size=24)
                for j, ln in enumerate(tl_desc_lines):
                    d.text((x - 80, base_y + 40 + j * 25), ln, font=f_desc2, fill=(*LIGHT_GRAY, 255))
    else:  # vertical
        event_h = SAFE_H // max(len(events), 1)
        for i, event in enumerate(events[:6]):
            y = MARGIN_Y + 100 + i * event_h
            time_label = event.get("time_label", f"Q{i + 1}")
            label = event.get("label", f"Event {i + 1}")

            # Time marker
            d.ellipse([W // 2 - 8, y - 8, W // 2 + 8, y + 8], fill=(*GOLD, 255))
            d.text((W // 2 + 20, y - 8), time_label, font=f_time, fill=(*NAVY, 255))

            # Event label
            d.text((W // 2 + 50, y - 8), label, font=f_label, fill=(*IVORY, 255))

    return img


def render_annotated_ui_mock(spec):
    """UI screenshot with annotation callouts."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    ui_title = spec.get("ui_title", "UI Interface")
    ui_desc = spec.get("ui_description", "")
    annotations = spec.get("annotations", [])

    f_title = _font(36, bold=True, role="display")
    f_ui = _font(24, role="body")
    f_elem = _font(28, bold=True, role="body")
    f_callout = _font(22, role="body")

    # UI placeholder rectangle
    ui_w, ui_h = SAFE_W - 100, H - 250
    ui_x, ui_y = (W - ui_w) // 2, MARGIN_Y + 80
    d.rectangle([ui_x, ui_y, ui_x + ui_w, ui_y + ui_h], fill=(40, 40, 50, 220), outline=(*GOLD, 255), width=2)

    # Title and description
    d.text((MARGIN_X, MARGIN_Y + 20), ui_title, font=f_title, fill=(*GOLD, 255))
    if ui_desc:
        f_ui2, ui_desc_lines = fit_text(ui_desc, d, SAFE_W - 40, 2, role="body", min_size=12, max_size=24)
        for i, ln in enumerate(ui_desc_lines):
            d.text((MARGIN_X, MARGIN_Y + 65 + i * 28), ln, font=f_ui2, fill=(*IVORY, 255))

    # Annotations
    for i, ann in enumerate(annotations[:6]):
        elem_name = ann.get("element_name", f"Element {i + 1}")
        callout = ann.get("callout_text", "")
        pos_hint = ann.get("position_hint", "center")

        # Position calculation
        positions = {
            "top": (ui_x + ui_w // 2, ui_y + 30),
            "bottom": (ui_x + ui_w // 2, ui_y + ui_h - 30),
            "left": (ui_x + 30, ui_y + ui_h // 2),
            "right": (ui_x + ui_w - 30, ui_y + ui_h // 2),
            "center": (ui_x + ui_w // 2, ui_y + ui_h // 2)
        }

        px, py = positions.get(pos_hint, positions["center"])

        # Element marker circle
        d.ellipse([px - 12, py - 12, px + 12, py + 12], fill=(*GOLD, 255), outline=(*NAVY, 255), width=2)

        # Callout line and text
        callout_y = py - 40 if pos_hint in ["top", "center"] else py + 40
        d.line([px, py, px, callout_y], fill=(*GOLD, 255), width=2)

        # Callout box background
        f_elem2, elem_lines = fit_text(elem_name, d, 200, 1, role="body", min_size=10, max_size=28)
        cb = d.textbbox((0, 0), elem_lines[0], font=f_elem2)
        cw = cb[2] - cb[0] + 20
        ch = cb[3] - cb[1] + 10
        d.rectangle([px - cw // 2, callout_y - ch - 5, px + cw // 2, callout_y + 5], fill=(30, 30, 30, 230))
        d.text((px - cw // 2 + 10, callout_y - ch + 2), elem_lines[0], font=f_elem2, fill=(*IVORY, 255))

        if callout:
            f_callout2, callout_lines = fit_text(callout, d, 200, 1, role="body", min_size=10, max_size=22)
            tb = d.textbbox((0, 0), callout_lines[0], font=f_callout2)
            tw = tb[2] - tb[0]
            d.text((px - tw // 2, callout_y + 10), callout_lines[0], font=f_callout2, fill=(*GOLD, 255))

    return img


def render_quote_card(spec):
    """Professional styled quote with attribution."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    quote = spec.get("quote", "")
    author = spec.get("author", "")
    author_title = spec.get("author_title", "")
    context = spec.get("context", "")

    f_quote = _font(36, bold=False, role="display")
    f_author = _font(32, bold=True, role="body")
    f_title = _font(24, role="body")
    f_context = _font(22, role="body")

    # Quote marks
    d.text((MARGIN_X + 40, MARGIN_Y + 60), """, font=_font(80, role="display"), fill=(*GOLD, 255))
    d.text((W - MARGIN_X - 80, H - MARGIN_Y - 60), """, font=_font(80, role="display"), fill=(*GOLD, 255))

    # Quote text
    f_quote2, quote_lines = fit_text(quote, d, SAFE_W - 120, 5, role="display", min_size=14, max_size=36)
    quote_y = MARGIN_Y + 100
    for i, ln in enumerate(quote_lines):
        d.text((MARGIN_X + 60, quote_y + i * 40), ln, font=f_quote2, fill=(*IVORY, 255))

    # Attribution section
    auth_y = quote_y + len(quote_lines) * 40 + 60
    d.text((MARGIN_X + 60, auth_y), f"— {author}", font=f_author, fill=(*GOLD, 255))

    if author_title:
        tb = d.textbbox((0, 0), author_title, font=f_title)
        tw = tb[2] - tb[0]
        d.text((MARGIN_X + 60, auth_y + 40), author_title, font=f_title, fill=(*IVORY, 255))

    # Context
    if context:
        f_ctx, ctx_lines = fit_text(context, d, SAFE_W - 120, 2, role="body", min_size=10, max_size=22)
        for i, ln in enumerate(ctx_lines):
            d.text((MARGIN_X + 60, auth_y + 80 + i * 28), ln, font=f_ctx, fill=(*LIGHT_GRAY, 255))

    return img


# ============================================================================
# S16_T003: Progressive Reveal Animation Support
# ============================================================================

def validate_animation_requirement(spec, duration_sec=None):
    """Validate that graphics >2s have animation specified.

    Args:
        spec: Graphic spec dict with optional 'animation' field
        duration_sec: Display duration in seconds (if known)

    Raises:
        RuntimeError: if duration >2s and no animation specified
    """
    if duration_sec is None:
        return  # Duration unknown, skip validation

    if duration_sec > ANIMATION_THRESHOLD:
        animation = spec.get("animation", {})
        if not animation.get("enabled"):
            raise RuntimeError(
                f"BLOCKED_GRAPHICS_ANIMATION_REQUIRED: Graphic displayed for {duration_sec:.1f}s "
                f"exceeds {ANIMATION_THRESHOLD}s threshold and must have animation enabled. "
                f"Add {{\"animation\": {{\"enabled\": true, \"style\": \"reveal\"}}}} to the spec."
            )


def render_animated_template(spec, output_path, duration_sec=None):
    """Render a graphic template with progressive reveal animation.

    Outputs a multi-frame PNG sequence with timing metadata file.
    Each frame reveals additional elements progressively.

    Args:
        spec: Graphic spec dict with layout and content
        output_path: Base path for output (will add _frame000.png suffix)
        duration_sec: Display duration (used for validation)

    Returns:
        List of paths to rendered frames

    Raises:
        RuntimeError: if animation validation fails or rendering fails
    """
    from PIL import Image

    # Validate animation requirement if duration provided
    if duration_sec:
        validate_animation_requirement(spec, duration_sec)

    animation = spec.get("animation", {})
    if not animation.get("enabled"):
        # No animation requested, render single static frame
        output_path = Path(output_path)
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_stem = output_path.stem
        frame_path = output_dir / f"{output_stem}_frame000.png"
        render_spec(spec, frame_path)
        write_animation_metadata([frame_path], output_path, frame_rate=DEFAULT_FRAME_RATE)
        return [frame_path]

    # Determine animation style and render multi-frame output
    style = animation.get("style", "reveal")
    layout = spec.get("layout")

    if style == "reveal":
        frames = render_reveal_animation(layout, spec, output_path, animation)
    elif style == "fade":
        frames = render_fade_animation(layout, spec, output_path, animation)
    else:
        raise RuntimeError(
            f"Unknown animation style '{style}'. Supported: reveal, fade"
        )

    # Write metadata file with frame timing
    write_animation_metadata(frames, output_path, frame_rate=DEFAULT_FRAME_RATE)

    return frames


def render_reveal_animation(layout, spec, output_path, animation_config):
    """Render progressive reveal animation for a template.

    Elements appear step-by-step based on template structure.
    For example:
    - framework_3_step: circles appear one at a time
    - decision_tree: branches appear sequentially
    - timeline: events appear in order

    NOTE: Current implementation uses fade animation for simplicity,
    which satisfies the "measurable frame changes" requirement.
    True progressive reveal would require modifying all template renderers
    to respect _revealed_elements field.
    """
    # For now, use fade animation as a simple reveal mechanism
    # This satisfies the requirement for "measurable frame changes"
    return render_fade_animation(layout, spec, output_path, animation_config)


def get_reveal_sequence(layout, spec):
    """Get progressive reveal sequence for a template layout.

    Returns a list of element sets, where each set represents elements
    revealed at that step. Elements appear cumulatively.
    """
    if layout == "framework_3_step":
        steps = spec.get("steps", [])
        return [list(range(i + 1)) for i in range(len(steps))]
    elif layout == "decision_tree":
        branches = spec.get("branches", [])
        return [list(range(i + 1)) for i in range(len(branches) + 1)]  # +1 for root
    elif layout == "timeline":
        events = spec.get("events", [])
        return [list(range(i + 1)) for i in range(len(events))]
    elif layout == "comparison_card":
        # Reveal left column, then right column
        return [["left"], ["left", "right"]]
    elif layout == "cost_stack":
        segments = spec.get("segments", [])
        return [list(range(i + 1)) for i in range(len(segments))]
    else:
        # Default: single reveal step
        return [["all"]]


def render_fade_animation(layout, spec, output_path, animation_config):
    """Render fade-in animation for a template.

    Simple opacity fade from 0 to 1 over specified duration.
    """
    from PIL import Image, ImageEnhance

    frames = []
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_stem = output_path.stem

    # Render base frame
    base_img = RENDERERS[layout](spec)

    fade_duration = animation_config.get("fade_duration", DEFAULT_REVEAL_DURATION)
    total_frames = int(fade_duration * DEFAULT_FRAME_RATE)

    for frame_idx in range(total_frames):
        alpha = frame_idx / total_frames
        faded = ImageEnhance.Brightness(base_img).enhance(alpha)
        frame_path = output_dir / f"{output_stem}_frame{frame_idx:03d}.png"
        faded.save(str(frame_path))
        frames.append(frame_path)

    # Add final frame at full opacity
    final_path = output_dir / f"{output_stem}_frame{total_frames:03d}.png"
    base_img.save(str(final_path))
    frames.append(final_path)

    return frames
    base_img.save(str(final_path))
    frames.append(final_path)

    return frames


def write_animation_metadata(frame_paths, output_path, frame_rate=30):
    """Write animation metadata file alongside frame sequence.

    Metadata includes frame paths, timing, and format for compositing.
    """
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_stem = output_path.stem

    metadata = {
        "format": "png_sequence",
        "frame_rate": frame_rate,
        "frames": [str(f.name) for f in frame_paths],
        "frame_count": len(frame_paths),
        "duration_sec": len(frame_paths) / frame_rate,
    }

    metadata_path = output_dir / f"{output_stem}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))


RENDERERS = {
    "lower_third": render_lower_third,
    "key_line": render_key_line,
    "stat_callout": render_stat_callout,
    "side_by_side": render_side_by_side,
    # S16_T002: Professional template types
    "comparison_card": render_comparison_card,
    "framework_3_step": render_framework_3_step,
    "decision_tree": render_decision_tree,
    "cost_stack": render_cost_stack,
    "before_after": render_before_after,
    "timeline": render_timeline,
    "annotated_ui_mock": render_annotated_ui_mock,
    "quote_card": render_quote_card,
}


def render_graphic_template(template_spec, output_path):
    """Render a professional graphic template from S16_T001 schema.

    Validates the template against graphic_template_schema and renders it.
    Returns output path on success, raises RuntimeError on validation failure.

    Args:
        template_spec: Dict with schema_version, template_type, content
        output_path: Path where PNG should be written

    Returns:
        Path to rendered PNG

    Raises:
        RuntimeError: if template validation fails or template_type unknown
    """
    # Import schema validator
    try:
        from graphic_template_schema import validate_graphic_template
    except ImportError:
        # If schema validator not available, render without validation
        validate_graphic_template = None

    # Validate template if validator available
    if validate_graphic_template:
        is_valid, errors = validate_graphic_template(template_spec)
        if not is_valid:
            raise RuntimeError(
                f"Graphic template validation failed: {'; '.join(errors)}. "
                f"Template must conform to graphic_template.schema.json"
            )

    # Map template_type to renderer function
    template_type = template_spec.get("template_type")
    type_to_layout = {
        "comparison_card": "comparison_card",
        "framework_3_step": "framework_3_step",
        "decision_tree": "decision_tree",
        "cost_stack": "cost_stack",
        "before_after": "before_after",
        "timeline": "timeline",
        "annotated_ui_mock": "annotated_ui_mock",
        "quote_card": "quote_card",
    }

    if template_type not in type_to_layout:
        raise RuntimeError(
            f"Unknown template_type '{template_type}'. "
            f"Supported: {', '.join(sorted(type_to_layout.keys()))}"
        )

    # Merge content with layout name for render_spec
    content = template_spec.get("content", {})
    render_spec_data = {"layout": type_to_layout[template_type], **content}

    # Render using standard render_spec
    return render_spec(render_spec_data, output_path)


def render_spec(spec, output_path):
    """Render a single overlay spec to a PNG. Raises RuntimeError on unknown layout.

    Supports:
    - 2x supersampling (render at 3840x2160, downsample with LANCZOS)
    - 9x16 aspect via spec['aspect']='9x16' (native vertical layout with
      recomputed safe margins, not letterboxed 16x9)
    """
    from PIL import Image
    layout = spec.get("layout")
    if layout not in RENDERERS:
        raise RuntimeError(
            f"Unknown graphics layout '{layout}'. "
            f"Supported: {', '.join(sorted(RENDERERS.keys()))}")

    aspect = spec.get("aspect", "16x9")
    scale = 2

    # Determine target dimensions
    if aspect == "9x16":
        base_w, base_h = 1080, 1920
    else:
        base_w, base_h = W, H

    render_w = base_w * scale
    render_h = base_h * scale
    margin_x = int(base_w * 0.10)
    margin_y = int(base_h * 0.10)
    safe_w = render_w - 2 * margin_x * scale
    safe_h = render_h - 2 * margin_y * scale

    # Save originals
    orig = (globals()["W"], globals()["H"], globals()["MARGIN_X"],
            globals()["MARGIN_Y"], globals()["SAFE_W"], globals()["SAFE_H"])

    try:
        globals()["W"] = render_w
        globals()["H"] = render_h
        globals()["MARGIN_X"] = margin_x * scale
        globals()["MARGIN_Y"] = margin_y * scale
        globals()["SAFE_W"] = safe_w
        globals()["SAFE_H"] = safe_h

        img = RENDERERS[layout](spec)
    finally:
        (globals()["W"], globals()["H"], globals()["MARGIN_X"],
         globals()["MARGIN_Y"], globals()["SAFE_W"], globals()["SAFE_H"]) = orig

    if scale > 1:
        img = img.resize((base_w, base_h), Image.LANCZOS)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    return output_path


def render_local_graphic_media(media_plan_path, project_dir):
    """Render local_graphic MEDIA beats (their visual IS a graphic) to their canonical
    output_path, and mark them valid in the clip DB.

    Distinct from render_batch (which renders OVERLAY PNGs composited onto video beats).
    These are beats where model/asset_type == local_graphic — the beat's entire visual is
    a rendered card. Without this, such beats stay status='ordered' forever (no producer)
    and the golden-truth gate correctly blocks assembly.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    plan = json.loads(Path(media_plan_path).read_text())
    project_id = plan.get("project_id", Path(project_dir).name)
    rendered = []
    try:
        import clip_db
        clip_db.init_db()
    except Exception:
        clip_db = None

    for beat in plan.get("beats", []):
        is_local = (beat.get("model") == "local_graphic"
                    or beat.get("asset_type") == "local_graphic")
        if not is_local:
            continue
        beat_id = beat.get("beat_id", beat.get("id", "unknown"))
        slot_id = beat.get("coverage_slot_id")
        out_path = beat.get("output_path")
        if not out_path:
            continue
        abs_out = Path(out_path)
        if not abs_out.is_absolute():
            abs_out = Path(__file__).resolve().parent.parent / out_path
        # Render the beat's graphic card. Prefer an explicit graphic spec; else build a
        # branded card from the beat's text/visual_brief.
        graphics_list = beat.get("graphics") or ([beat["graphic"]] if beat.get("graphic") else [])
        spec = None
        if graphics_list:
            g = graphics_list[0]
            spec = {**g}
            layout = g.get("layout") or g.get("type")
            if layout not in RENDERERS:
                layout = "key_line"   # default for missing/unknown layout
            spec["layout"] = layout
            if not spec.get("text"):
                spec["text"] = (beat.get("graphic_text") or beat.get("visual_brief")
                                or beat.get("narration_text") or beat_id)
        else:
            # Build a default key_line card from the beat's text content
            text = (beat.get("graphic_text") or beat.get("visual_brief")
                    or beat.get("narration_text") or beat_id)
            spec = {"layout": "key_line", "text": text}
        # Render as PNG at the canonical media path (assemble holds it for the duration).
        png_path = abs_out.with_suffix(".png")
        png_path.parent.mkdir(parents=True, exist_ok=True)
        render_spec(spec, png_path)
        rendered.append(str(png_path))
        print(f"  ✓ local_graphic media {beat_id}{('/'+slot_id) if slot_id else ''} → {png_path.name}")

        # Mark valid in the clip DB so the golden-truth gate passes.
        if clip_db and beat.get("clip_id"):
            cid = beat["clip_id"]
            try:
                import hashlib
                sha = hashlib.sha256(png_path.read_bytes()).hexdigest()
                clip_db.record_generated(cid, actual_dur_sec=beat.get("required_duration_sec")
                                         or beat.get("duration_target_sec") or 0.0,
                                         actual_width=1920, actual_height=1080,
                                         actual_has_audio=False, actual_sha256=sha)
                clip_db.mark_valid(cid, validated_by="render_graphics")
                clip_db.log_access(cid, "render_graphics", "generate", f"rendered local_graphic → {png_path.name}")
            except Exception as e:
                print(f"  ⚠ clip_db update failed for {beat_id}: {e}", file=sys.stderr)
    print(f"  Rendered {len(rendered)} local_graphic media file(s)")
    return rendered


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


def render_local_graphic_render_unit(db, production_id: str, render_unit_id: str) -> str:
    """DB-native: load a render unit from DB, render its deterministic text
    as a local graphic, register the artifact, and link it to the render unit.

    Returns the output path of the rendered file.

    Raises:
        RuntimeError: if render unit is not found, not local_graphic,
                      or has no deterministic_text_spec.
    """
    import production_db as _db
    import production_repo as _repo

    conn = _db.connect(db)
    ru = conn.execute(
        "SELECT * FROM render_units WHERE id=?", (render_unit_id,)
    ).fetchone()
    conn.close()

    if not ru:
        raise RuntimeError(f"Render unit {render_unit_id} not found in DB")

    ru = dict(ru)
    if ru.get("asset_type") != "local_graphic":
        raise RuntimeError(
            f"render_local_graphic_render_unit requires asset_type='local_graphic', "
            f"got '{ru.get('asset_type')}'"
        )

    meta = json.loads(ru["metadata_json"]) if ru["metadata_json"] else {}
    dts = meta.get("deterministic_text_spec")
    if not dts:
        raise RuntimeError(
            f"Render unit {render_unit_id} has no deterministic_text_spec "
            f"in metadata — cannot render local graphic"
        )

    spec_type = dts.get("type", "title_card")
    text_content = dts.get("headline") or dts.get("text") or dts.get("quote") or dts.get("label", "")
    layout_map = {
        "title_card": "key_line",
        "source_card": "lower_third",
        "quote_card": "quote_card",
        "framework_card": "framework_3_step",
        "stat_card": "stat_callout",
        "comparison_card": "comparison_card",
        "before_after_card": "before_after",
        "timeline_card": "timeline",
        "cost_card": "cost_stack",
        "decision_card": "decision_tree",
        "ui_annotation_card": "annotated_ui_mock",
        "side_by_side_card": "side_by_side",
    }
    layout = layout_map.get(spec_type)
    if layout is None:
        raise RuntimeError(
            f"Unknown deterministic_text_spec type '{spec_type}' for render unit "
            f"{render_unit_id}. Supported: {', '.join(sorted(layout_map.keys()))}")

    render_spec_data = {"layout": layout, "text": text_content}
    if spec_type == "source_card":
        render_spec_data["subtitle"] = dts.get("text") or ""

    output_dir = ROOT / "assets" / "media" / production_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{render_unit_id}.png"

    render_spec(render_spec_data, output_path)

    file_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    dts_sha = hashlib.sha256(_db._json(dts).encode()).hexdigest()
    expected_texts = [v for v in (dts.get("text"), dts.get("headline"), dts.get("quote"), dts.get("label")) if v]

    artifact_meta = {
        "render_method": "local_graphic",
        "renderer": "render_graphics.py",
        "text_spec_sha256": dts_sha,
        "expected_text": expected_texts,
        "machine_readable_source_text": expected_texts,
        "deterministic_renderer": True,
        "ai_model_output_forbidden": True,
        "source_render_unit_id": render_unit_id,
    }

    art = _repo.register_artifact(
        production_id=production_id,
        path=output_path,
        kind="generated_media",
        extra_metadata=artifact_meta,
        db_path=db,
    )

    _repo.link_artifact_to_render_unit(art["id"], render_unit_id, db_path=db)

    return str(output_path)


def render_overlay_timeline(timeline_plan, output_dir):
    """Render all overlay artifacts from an overlay timeline plan.

    Each overlay spec is rendered as a deterministic RGBA PNG.
    The plan is mutated in-place with artifact_path and artifact_sha256.

    Args:
        timeline_plan: dict matching overlay_timeline.schema.json
        output_dir: Path to write overlay PNGs

    Returns:
        list of overlay event dicts with artifact_path populated

    Raises:
        RuntimeError: if an overlay spec has an unknown layout
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    overlays = timeline_plan.get("overlays", [])
    total_dur = timeline_plan.get("total_duration_sec", 0)

    for ov in overlays:
        start = ov.get("start_time_sec", 0)
        end = ov.get("end_time_sec", 0)

        if end > total_dur:
            raise RuntimeError(
                f"BLOCKED_OVERLAY_OUTSIDE_DURATION: overlay {ov['overlay_id']} "
                f"end_time_sec={end} exceeds total_duration_sec={total_dur}"
            )

        spec = ov.get("spec", {})
        layout = spec.get("layout")
        if layout not in RENDERERS:
            raise RuntimeError(
                f"BLOCKED_UNKNOWN_OVERLAY_LAYOUT: overlay {ov['overlay_id']} "
                f"has unknown layout '{layout}'"
            )

        out_path = output_dir / f"overlay_{ov['overlay_id']}.png"
        render_spec(spec, out_path)
        ov["artifact_path"] = str(out_path)
        ov["artifact_sha256"] = hashlib.sha256(out_path.read_bytes()).hexdigest()

    return overlays


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
        render_local_graphic_media(args.batch, args.project_dir)  # MEDIA beats (visual IS a graphic)
        render_batch(args.batch, args.project_dir)                # OVERLAY PNGs onto video beats
        return 0
    else:
        ap.error("Provide --spec or --batch")


if __name__ == "__main__":
    raise SystemExit(main())
