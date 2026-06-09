#!/usr/bin/env python3
"""generate_reference_assets.py — Generate all reference still images.

Usage: python3 generate_reference_assets.py [--batch A|B|C|D|E] [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF = ROOT / "node_modules" / "@higgsfield" / "cli" / "bin" / "higgsfield.js"
RESULTS_LOG = ROOT / "docs" / "reference_assets" / "REFERENCE_GENERATION_RESULTS.md"
JAMES_REF = str(ROOT / "brand" / "James_harrington_front.png")
JAMES_34  = str(ROOT / "brand" / "James_harrington_3_4.png")
JAMES_SIDE = str(ROOT / "brand" / "James_harrington_side.png")
JAMES_VERT = str(ROOT / "brand" / "James_harrington_vertical.png")

NEG = ("no futuristic holograms, no cyberpunk, no neon, no floating UI, no robots, "
       "no garbled text, no readable generated text, no fake logos, no distorted hands, "
       "no uncanny valley faces, no sci-fi, no overdesigned office, no ring light, "
       "no colored gels, no visible brand logos, no beard, no glasses, no age drift, "
       "no random smiling stock photo people, no seamless white backdrop")

ASSETS = {
    "A": [  # James anchors — Soul V2
        ("JAMES_THREE_QUARTER_STUDY_001", "text2image_soul_v2",
         "Same 60-year-old British man, 3/4 angle turned slightly right, looking thoughtfully off-camera mid-thought. Private study, warm lamp. Navy cashmere sweater over white Oxford. Slight knowing expression, composed. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_THREE_QUARTER_STUDY_001.png", JAMES_34),
        ("JAMES_SIDE_PROFILE_001", "text2image_soul_v2",
         "Same 60-year-old British man, full side profile facing left, looking toward implied window or downward. Private study. Warm lamp rim light. Navy sweater. Composed bearing. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_SIDE_PROFILE_001.png", JAMES_SIDE),
        ("JAMES_VERTICAL_CLOSEUP_001", "text2image_soul_v2",
         "Same 60-year-old British man, head and shoulders, facing camera directly. Dark navy background, soft warm key light from left. Navy cashmere, open collar. Composed direct expression. Hyperrealistic, 4K. 9:16 portrait.",
         "assets/reference/james/JAMES_VERTICAL_CLOSEUP_001.png", JAMES_VERT),
    ],
    "B": [  # Studio master
        ("STUDIO_LIBRARY_WIDE_001", "flux_2",
         "Wide establishing shot of a private executive library and home office. Substantial dark wood desk, center-left. Floor-to-ceiling dark wood bookshelves, books well-used not decorative. Directional brass desk lamp, warm golden light from left. Dark leather upholstered chair. Window suggesting warm afternoon light. Desk: leather notebook, pen, papers, ceramic mug. Palette: deep navy, warm cream, dark wood, aged brass, leather, charcoal. No visible technology. No logos. Books in soft focus, spines not readable. Warm intelligent atmosphere. Cinematic hyperrealistic photography. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_WIDE_001.png", None),
        ("STUDIO_LIBRARY_EMPTY_ROOM_001", "flux_2",
         "Same private executive library — empty of people. Dark wood desk, bookshelves, brass lamp, leather chair all present. Warm morning light. Leather notebook and pen on desk. Same palette and layout as the wide shot. Still, intelligent, waiting atmosphere. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_EMPTY_ROOM_001.png", None),
    ],
    "C": [  # Remaining studio
        ("STUDIO_LIBRARY_CLOSEUP_DESK_001", "flux_2",
         "Close-up of dark wood desk surface in warm private library. Dark leather notebook, pen, printed documents with margin notes, plain ceramic mug. Edge of brass desk lamp. No readable text. Warm palette. Shallow depth of field — bookshelves very soft behind. Hyperrealistic still life, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_CLOSEUP_DESK_001.png", None),
        ("STUDIO_LIBRARY_WINDOW_LIGHT_001", "flux_2",
         "Same private executive library. Late afternoon golden light streaming through a window on the left. Warm amber and cream light falls across desk and bookshelves. Empty of people. Dust motes optional. Warm contemplative private atmosphere. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_WINDOW_LIGHT_001.png", None),
        ("STUDIO_LIBRARY_NIGHT_LAMP_001", "flux_2",
         "Same private executive library in the evening. Brass desk lamp as primary light source — warm gold circle on desk, falling into shadow. Window shows dark sky. Bookshelves recede into shadow. Intimate, focused, serious. No neon. Same furniture and layout. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_NIGHT_LAMP_001.png", None),
        ("STUDIO_LIBRARY_READING_CHAIR_001", "flux_2",
         "Corner of same private library. Dark leather wingback or upholstered reading chair, slightly worn. Small side table with lamp and ceramic mug. Open book on the arm. Warm practical lamp light. Bookshelves in background. No person present. Quiet intimate reading space. Same palette: dark wood, leather, cream, brass. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_READING_CHAIR_001.png", None),
        ("STUDIO_LIBRARY_BOOKSHELF_DETAIL_001", "flux_2",
         "Close-up of dark wood bookshelves in private library. Books varying heights, well-used, not decorative. Spines visible but blurred — titles not readable, shallow depth of field. Small framed document on one shelf (not readable). Warm lamp light, side shadows. No garbled AI text. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_BOOKSHELF_DETAIL_001.png", None),
    ],
    "D": [  # Remaining James
        ("JAMES_STANDING_LIBRARY_001", "text2image_soul_v2",
         "Same 60-year-old British man, standing upright near floor-to-ceiling dark wood bookshelves in his private library. Navy blazer over white Oxford shirt. 3/4 angle toward camera. Hands naturally at sides or holding a closed book. Warm lamp light from left. Books in soft focus, not readable. Composed natural standing posture. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_STANDING_LIBRARY_001.png", JAMES_REF),
        ("JAMES_OVER_SHOULDER_WRITING_001", "text2image_soul_v2",
         "Over-the-shoulder view. James's back and shoulder in navy cashmere sweater in foreground. Dark leather notebook open on desk, pen in right hand making an annotation. Warm brass lamp light on desk. Same private study, dark wood desk. Camera slightly above, angled down. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_OVER_SHOULDER_WRITING_001.png", JAMES_REF),
        ("JAMES_DESK_THINKING_001", "text2image_soul_v2",
         "Same 60-year-old British man seated at dark wood desk, looking down or slightly off-camera. Pen held lightly in one hand. Thoughtful absorbed expression — mid-consideration. Navy cashmere sweater, white Oxford. Lamp light warm from left. Bookshelves soft-focus behind. Quiet intellectual focus. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_DESK_THINKING_001.png", JAMES_REF),
        ("JAMES_WALKING_HOME_LIBRARY_001", "text2image_soul_v2",
         "Same 60-year-old British man in purposeful slow walk through his private library. Navy blazer over white Oxford. Slight 3/4 angle. Bookshelves and warm lamp in background. Not looking at camera. Composed bearing. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_WALKING_HOME_LIBRARY_001.png", JAMES_REF),
        ("JAMES_CASUAL_HOME_OFFICE_001", "text2image_soul_v2",
         "Same 60-year-old British man, seated, slightly relaxed but still elegant. Mid-grey fine-knit sweater over cream Oxford shirt, no blazer. Same warm private study. Same composed demeanor — slightly more at ease, quiet morning working session. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_CASUAL_HOME_OFFICE_001.png", JAMES_REF),
        ("JAMES_FORMAL_DARK_JACKET_001", "text2image_soul_v2",
         "Same 60-year-old British man, seated, dark charcoal blazer over white shirt, optional subtle pocket square. More formal register — serious, measured. Same private study. Composed expression with more gravity than usual. Hyperrealistic, 4K. 16:9.",
         "assets/reference/james/JAMES_FORMAL_DARK_JACKET_001.png", JAMES_REF),
        ("STUDIO_LIBRARY_MEDIUM_DESK_001", "text2image_soul_v2",
         "Medium shot chest-up. 60-year-old British man in navy cashmere sweater seated at dark wood desk. Eye-level. Desk surface: notebook, pen. Brass lamp from left. Dark bookshelves soft-focus behind. Same private library. Composed, attentive. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_MEDIUM_DESK_001.png", JAMES_REF),
        ("STUDIO_LIBRARY_OVER_SHOULDER_001", "text2image_soul_v2",
         "Over-the-shoulder in private library. Same 60-year-old British man (back and right shoulder in navy sweater). Looking at dark wood desk: open leather notebook, pen, papers. Brass lamp light. Slightly high angle, static. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_OVER_SHOULDER_001.png", JAMES_REF),
        ("STUDIO_LIBRARY_SIDE_PROFILE_001", "text2image_soul_v2",
         "Side angle: same 60-year-old British man seated at dark wood desk. Bookshelves in soft focus behind. Brass lamp warm light. Navy sweater. Looking slightly downward or toward implied window. Same private library. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_SIDE_PROFILE_001.png", JAMES_SIDE),
        ("STUDIO_LIBRARY_STANDING_BOOKSHELF_001", "text2image_soul_v2",
         "Same 60-year-old British man in navy blazer, standing near floor-to-ceiling dark wood bookshelves. 3/4 angle. Holding a closed book or hands at sides. Warm lamp light. Books soft-focus, not readable. Same room as wide establishing shot. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_STANDING_BOOKSHELF_001.png", JAMES_REF),
        ("STUDIO_LIBRARY_CAT_BACKGROUND_001", "text2image_soul_v2",
         "Medium desk shot: 60-year-old British man in navy sweater at dark wood desk. Warm lamp. In deep background on a dark chair, a blue-grey British Shorthair cat sleeping quietly. The cat barely noticeable, deep background, low luminance, not facing camera. Hyperrealistic, 4K. 16:9.",
         "assets/reference/studio_library/STUDIO_LIBRARY_CAT_BACKGROUND_001.png", JAMES_REF),
    ],
    "E": [  # Cat references
        ("CAT_LIBRARY_SLEEPING_001", "flux_2",
         "A blue-grey British Shorthair cat sleeping deeply on a dark leather or fabric chair in a warm private library. Compact round-faced, dense plush blue-grey fur, curled up completely at rest, eyes closed. Background: bookshelves, warm lamp. The cat is in the background, not foreground. Quiet domestic detail. Hyperrealistic, 4K. 16:9.",
         "assets/reference/cat/CAT_LIBRARY_SLEEPING_001.png", None),
        ("CAT_WINDOW_001", "flux_2",
         "Same blue-grey British Shorthair cat, sitting quietly on a windowsill in the private library. Looking out the window away from camera. Warm afternoon light on its fur. Room visible in background: dark wood desk, bookshelves. Calm, self-contained. Hyperrealistic, 4K. 16:9.",
         "assets/reference/cat/CAT_WINDOW_001.png", None),
        ("CAT_BOOKSHELF_BACKGROUND_001", "flux_2",
         "Same blue-grey British Shorthair cat, settled on the floor near the base of dark wood bookshelves in the private library. Relaxed posture. Barely visible in background. Books above, lamp light from one side. The cat is a minor detail, not focal point. Hyperrealistic, 4K. 16:9.",
         "assets/reference/cat/CAT_BOOKSHELF_BACKGROUND_001.png", None),
    ],
}


def hf_generate(model, prompt, output_path, ref_image=None, dry_run=False):
    cmd = ["node", str(HF), "generate", "create", model,
           "--prompt", prompt, "--wait", "--json"]
    if ref_image and Path(ref_image).exists():
        cmd += ["--image", ref_image]

    if dry_run:
        print(f"    DRY RUN: {model} → {output_path}")
        if ref_image:
            print(f"    ref: {Path(ref_image).name}")
        return True

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"    FAILED: {r.stdout[:200]}", file=sys.stderr)
        return False

    data = json.loads(r.stdout)
    if isinstance(data, list):
        data = data[0]
    url = data.get("result_url") or data.get("output_url", "")
    if not url:
        print(f"    FAILED: no URL in response", file=sys.stderr)
        return False

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, output_path)
    size = os.path.getsize(output_path)
    print(f"    saved: {Path(output_path).name} ({size//1024}KB)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="all", help="A|B|C|D|E|all")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    batches = list(ASSETS.keys()) if args.batch == "all" else args.batch.upper().split(",")
    results = []

    for batch in batches:
        if batch not in ASSETS:
            print(f"Unknown batch: {batch}")
            continue
        print(f"\n=== Batch {batch} ===")
        for (asset_id, model, prompt, out_path, ref) in ASSETS[batch]:
            if Path(out_path).exists() and not args.dry_run:
                print(f"  [{asset_id}] already exists — skip")
                results.append((asset_id, out_path, "skipped"))
                continue
            print(f"  [{asset_id}] {model}...", end=" ", flush=True)
            ok = hf_generate(model, prompt, out_path, ref, dry_run=args.dry_run)
            status = "generated" if ok else "failed"
            results.append((asset_id, out_path, status))

    # Summary
    print(f"\n--- Results ---")
    for (aid, path, status) in results:
        print(f"  {status:10s} {aid}")
    gen = sum(1 for _, _, s in results if s == "generated")
    skipped = sum(1 for _, _, s in results if s == "skipped")
    failed = sum(1 for _, _, s in results if s == "failed")
    print(f"\n  generated={gen} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
