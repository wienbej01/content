#!/usr/bin/env python3
"""generate_navy_lipsync_angles.py — fill the G14 gap: two missing navy-sweater
hero lipsync reference angles (three_quarter + side_profile) in the library setting,
then AUTO-DOWNLOAD them to their registered canonical paths.

These complete the `navy_sweater_library` active_set in configs/james/model_routing.yaml
so hero_lipsync beats can rotate across >=3 angles in the brand-default wardrobe
(navy sweater / white Oxford), matching JAMES_MEDIUM_FRONT_NAVY_SWEATER_002.

Method: image-to-image off the existing FRONT navy frame via nano_banana_2 (the same
model + 16:9 1376x768 framing used for the other canonical James frames), so identity,
wardrobe, and the library setting carry over — only the camera angle changes. The result
URL from the --wait --json job is downloaded straight to the target filename.

SPEND: each gen is one nano_banana_2 image job. Default is --dry-run (prints the exact
CLI, zero spend). Pass --execute to generate + download. This is the small image-gen
budget flagged as the Fable G14 escalation.

Usage:
  python3 scripts/generate_navy_lipsync_angles.py            # dry-run (zero spend)
  python3 scripts/generate_navy_lipsync_angles.py --execute  # generate + auto-download
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF = ROOT / "node_modules" / "@higgsfield" / "cli" / "bin" / "higgsfield.js"
CANON = ROOT / "assets" / "reference" / "james" / "canonical"

MODEL = "nano_banana_2"   # job_set_type nano_banana_flash; used for all canonical James frames
IDENTITY_REF = CANON / "JAMES_MEDIUM_FRONT_NAVY_SWEATER_002.png"

# Match the established prompt style (SAME EXACT MAN + reference image + angle change).
ANCHOR = (
    "SAME EXACT MAN from the reference image. Maintain identical identity, face, and "
    "silver-grey hair combed back. ~60-year-old British gentleman, calm composed expression. "
    "Wearing a navy fine-knit sweater over an open-collar pale-blue/white Oxford shirt — "
    "identical wardrobe to the reference. Use the SAME room as the reference image: a warm "
    "private home library with white bookshelves, a brass anglepoise desk lamp at left, a "
    "framed print on the wall, soft warm window light. Warm navy/cream/dark-wood palette, "
    "motivated practical lighting. Photorealistic, cinematic, 16:9."
)

TARGETS = [
    (
        "JAMES_THREE_QUARTER_NAVY_SWEATER_002",
        "Change the camera angle to a three-quarter view: the man turned about 30 degrees to "
        "his right, looking thoughtfully toward the camera mid-thought, head and shoulders. " + ANCHOR,
        CANON / "JAMES_THREE_QUARTER_NAVY_SWEATER_002.png",
    ),
    (
        "JAMES_SIDE_PROFILE_NAVY_SWEATER_002",
        "Change the camera angle to a full left side profile: the man facing left toward the "
        "implied window, calm and composed, head and shoulders, warm lamp rim light on the face. " + ANCHOR,
        CANON / "JAMES_SIDE_PROFILE_NAVY_SWEATER_002.png",
    ),
]


def build_cmd(prompt: str) -> list[str]:
    return [
        "node", str(HF), "generate", "create", MODEL,
        "--prompt", prompt,
        "--image", str(IDENTITY_REF),
        "--aspect_ratio", "16:9",
        "--wait", "--json",
    ]


def _extract_result_url(stdout: str) -> str | None:
    """Pull the first result_url from the CLI's --json output (object or array)."""
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        # CLI may print multiple JSON blocks / log lines; scan for the last {...}/[...]
        import re
        for m in reversed(re.findall(r"(\{.*\}|\[.*\])", stdout, re.S)):
            try:
                data = json.loads(m)
                break
            except json.JSONDecodeError:
                continue
        else:
            return None

    def find_url(o):
        if isinstance(o, dict):
            if o.get("result_url"):
                return o["result_url"]
            for v in o.values():
                u = find_url(v)
                if u:
                    return u
        elif isinstance(o, list):
            for v in o:
                u = find_url(v)
                if u:
                    return u
        return None
    return find_url(data)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ytchannel-refgen"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if not data:
        raise RuntimeError(f"empty download from {url}")
    dest.write_bytes(data)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate + auto-download the 2 missing navy lipsync angles (G14).")
    ap.add_argument("--execute", action="store_true",
                    help="Actually generate + download (spends image-gen credits). Default is dry-run.")
    args = ap.parse_args(argv)

    if not IDENTITY_REF.exists():
        print(f"ERROR: identity reference not found: {IDENTITY_REF}", file=sys.stderr)
        return 1

    made = 0
    for asset_id, prompt, out_path in TARGETS:
        cmd = build_cmd(prompt)
        print(f"\n=== {asset_id} -> {out_path.relative_to(ROOT)} ===")
        if out_path.exists():
            print("  already exists; skipping (delete to regenerate).")
            continue
        if not args.execute:
            print("  DRY-RUN (zero spend). Command:")
            print("   ", " ".join(f'"{c}"' if " " in c else c for c in cmd))
            continue
        print("  generating via nano_banana_2 (image-to-image off front navy frame)…")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            print(f"  FAILED (exit {r.returncode}): {r.stderr[-400:]}", file=sys.stderr)
            return 1
        url = _extract_result_url(r.stdout)
        if not url:
            print(f"  ERROR: no result_url in output:\n{r.stdout[-500:]}", file=sys.stderr)
            return 1
        print(f"  result: {url}")
        _download(url, out_path)
        sz = out_path.stat().st_size // 1024
        print(f"  ✓ downloaded -> {out_path.relative_to(ROOT)} ({sz}KB)")
        made += 1

    if not args.execute:
        print("\nDRY-RUN complete — zero Higgsfield spend. Re-run with --execute to generate + download.")
    else:
        print(f"\n✓ {made} frame(s) generated + downloaded.")
        print("Next: flip configs/james/model_routing.yaml -> active_set: navy_sweater_library, then recompile + refresh gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
