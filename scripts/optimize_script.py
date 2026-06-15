#!/usr/bin/env python3
"""optimize_script.py — Takeaway-emphasis optimization stage.

A reusable pipeline stage (runs AFTER a raw script is written, BEFORE storyboard)
that makes educational videos land their takeaways. It:

  1. Identifies the 2-4 KEY TAKEAWAYS the video builds toward (LLM, sonnet_creative).
  2. Marks each as a key_point with an emphasis 'treatment':
        - hero_payoff      : the single biggest landing → James to camera + gesture
        - overlay_on_broll : a supporting takeaway → on-screen text over b-roll
  3. Writes a natural-pacing 'tts_text' per segment: pacing comes from PUNCTUATION
     (em-dashes, ellipses, sentence breaks), NOT stacked <break> tags (which make
     ElevenLabs choppy). At most ONE <break> per key point, before the payoff.
  4. Specifies the on-screen GRAPHIC for each takeaway (a concise key_line or a
     small bulleted list/framework).

Downstream alignment (already wired):
  - storyboard.py:_apply_key_point_emphasis reads key_points → hero/overlay/pause
  - tts.py reads tts_text → natural audio emphasis
  - render_graphics.py renders the key_line / framework overlays

Usage:
  python3 scripts/optimize_script.py scripts/generated/raw.json --output enriched.json
  python3 scripts/optimize_script.py scripts/generated/raw.json --dry-run
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MAX_KEY_POINTS = 4


def _split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+', (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def build_prompt(script):
    """Build the LLM optimization prompt from the raw script."""
    segments = [{"id": s["id"], "text": s.get("text", "")} for s in script.get("segments", [])]
    title = script.get("title", "")
    return (
        "You are an editor optimizing an EDUCATIONAL YouTube video script so its key "
        "takeaways LAND and are remembered. The script's facts are already verified — "
        "DO NOT add, remove, or alter any factual claim, statistic, name, or citation. "
        "You only restructure pacing and mark emphasis.\n\n"
        "TASKS:\n"
        "1. Identify the 2-4 KEY TAKEAWAYS this video builds toward (the things a viewer "
        "should remember). Prefer the conclusion/payoff lines and the core principle.\n"
        "2. Choose ONE as the primary payoff (treatment 'hero_payoff'); the rest are "
        "'overlay_on_broll'.\n"
        "3. For EACH takeaway provide an 'overlay': either {kind:'key_line', text:'...'} "
        "for a single punchy line, or {kind:'framework', title:'...', items:[...], "
        "highlight_index:N} for a 2-4 item list. Overlay text must be SHORT (fits on "
        "screen), may use \\n for line breaks. No more than 4 items.\n"
        "4. Rewrite each segment's delivery as 'tts_text' — treat PUNCTUATION as musical "
        "notation that forces the voice to emote, pause, and emphasize. PACING + EMPHASIS "
        "RULES:\n"
        "   - DO NOT USE <break> TAGS. They distort prosody (slow the word before, rush the "
        "words after). FORBIDDEN.\n"
        "   - ELLIPSES (...) = a trailing, thoughtful pause. Use mid-sentence before a "
        "reveal: 'But that speed... has a hidden price.'\n"
        "   - EM-DASH (—) = an abrupt, contrasting shift between two independent clauses "
        "ONLY. Never for a light mid-phrase pause (use a comma). Em-dash renders LONG — use "
        "rarely.\n"
        "   - ALL CAPS = sharp emphasis (volume/sharpness) on a key word. This is the "
        "primary emphasis mechanism and is SAFE at the locked low style. Use on 1-3 key "
        "words per segment (e.g. ACTUALLY, LESS, BURN, ENERGY). Never caps a whole phrase.\n"
        "   - \"QUOTATION MARKS\" = make the voice slow down and articulate a named concept.\n"
        "   - PARAGRAPH BREAKS (\\n\\n) reset cadence between distinct ideas — but NEVER "
        "place a paragraph break immediately after a sentence that ENDS A COMMA-LIST "
        "(e.g. '...stress, frustration, and effort.'); the voice drags the final list word. "
        "Instead bridge into the next thought with an em-dash, or add a few trailing words.\n"
        "   - SPELL OUT numbers (twenty, not 20) for smoother cadence.\n"
        "   - Short punchy payoff sentences should be their own sentence after an ellipsis "
        "on the prior clause; do NOT cram emphasis with tags.\n"
        "   - Keep the spoken words identical in MEANING to the display text (caps/quotes/"
        "ellipses are delivery cues, not new words).\n\n"
        "Return ONLY JSON:\n"
        "{\n"
        '  "key_points": [\n'
        '    {"text": "<exact sentence from the script>", "treatment": "hero_payoff|overlay_on_broll",\n'
        '     "pause_before_sec": 0.6, "hero_gesture": "<gesture if hero_payoff, else null>",\n'
        '     "overlay": {"kind": "key_line|framework", ...}}\n'
        "  ],\n"
        '  "tts_blocks": [\n'
        '    {"type": "intro_hook|factual_data|the_climax|the_punchline|...",\n'
        '     "text": "<grouped sentences with internal <break time=\\"1.0s\\"/> tags>",\n'
        '     "pause_ms": <small gap after block>, "stability": <0-1>, "style": <0-1>}\n'
        "  ]\n"
        "}\n\n"
        "TTS_BLOCKS RULES (chunk-and-stitch V2 — dynamic emotion + native pacing):\n"
        "  - Use FEW, LARGE blocks (typically 3-5) that group LOGICALLY CONNECTED "
        "sentences. This preserves the emotional ARC — the model reads ahead and carries "
        "pitch/intensity across the block (isolating every sentence makes it flat).\n"
        "  - Pace INSIDE a block with native <break time=\"Xs\" /> tags (0.5-1.5s). The "
        "model reads across them without losing the arc.\n"
        "  - Give each block PER-BLOCK voice settings to shift emotion:\n"
        "      factual/data: stability 0.6-0.7, style 0.0 (crisp, authoritative)\n"
        "      hook/reveal:  stability 0.40, style 0.15-0.25 (intriguing)\n"
        "      climax/turn:  stability 0.35, style 0.25-0.35 (grave, emotional)\n"
        "      punchline/cta: stability 0.45, style 0.15 (impassioned but controlled)\n"
        "  - pause_ms is a SMALL gap AFTER the block (200-500ms); most pacing is the "
        "internal break tags.\n"
        "  - Use CAPS for 1-3 emphasis words per block (ACTUALLY, BURN, ENERGY).\n"
        "  - Concatenated block texts must equal the script's spoken content.\n\n"
        f"TITLE: {title}\n"
        f"SCRIPT SEGMENTS:\n{json.dumps(segments, indent=2)}")


def _deterministic_fallback(script):
    """No-LLM fallback: mark the LAST sentence as the hero payoff, second-to-last
    distinctive sentence as a supporting overlay. Pacing left as-is. Used when the
    LLM is unavailable so the pipeline never blocks."""
    segs = script.get("segments", [])
    all_sentences = []
    for s in segs:
        for sent in _split_sentences(s.get("text", "")):
            all_sentences.append((s["id"], sent))
    if not all_sentences:
        return {"key_points": [], "segments": []}
    kps = []
    last_id, last_sent = all_sentences[-1]
    kps.append({
        "text": last_sent, "treatment": "hero_payoff", "pause_before_sec": 0.6,
        "hero_gesture": "open, settling hand gesture on the closing line",
        "overlay": {"kind": "key_line", "text": last_sent[:60]},
    })
    return {"key_points": kps, "segments": []}


def optimize(script, dry_run=False, use_llm=True):
    """Return (enriched_script, meta). Adds key_points + tts_text. Pure function on a dict."""
    enriched = json.loads(json.dumps(script))  # deep copy
    meta = {"source": "llm"}

    data = None
    if use_llm and not dry_run:
        try:
            from llm_call import llm_call
            data, _, _, _ = llm_call(task="storyboard_generation",
                                     prompt=build_prompt(script), expect_json=True)
        except Exception as e:  # noqa - never block the pipeline on LLM failure
            meta = {"source": "fallback", "llm_error": str(e)}
    if dry_run:
        return enriched, {"source": "dry_run", "prompt_chars": len(build_prompt(script))}

    if not data or not isinstance(data, dict) or not data.get("key_points"):
        data = _deterministic_fallback(script)
        meta = {"source": "fallback", **({} if "llm_error" not in meta else {"llm_error": meta["llm_error"]})}

    # Validate + clamp key points
    kps = []
    for kp in (data.get("key_points") or [])[:MAX_KEY_POINTS]:
        if not isinstance(kp, dict) or not kp.get("text"):
            continue
        treatment = kp.get("treatment", "overlay_on_broll")
        if treatment not in ("hero_payoff", "overlay_on_broll"):
            treatment = "overlay_on_broll"
        ov = kp.get("overlay") or {}
        emphasis = {
            "treatment": treatment,
            "pause_before_sec": float(kp.get("pause_before_sec", 0.6) or 0.6),
            "overlay": ov,
        }
        if treatment == "hero_payoff" and kp.get("hero_gesture"):
            emphasis["hero_gesture"] = kp["hero_gesture"]
        kps.append({"text": kp["text"].strip(), "emphasis": emphasis})

    # Enforce: at most ONE hero_payoff (the single biggest landing)
    hero_seen = False
    for kp in kps:
        if kp["emphasis"]["treatment"] == "hero_payoff":
            if hero_seen:
                kp["emphasis"]["treatment"] = "overlay_on_broll"
                kp["emphasis"].pop("hero_gesture", None)
            hero_seen = True
    enriched["key_points"] = kps

    # Merge tts_blocks (chunk-and-stitch V2). Keep native <break> tags + per-block settings.
    blocks = []
    for b in (data.get("tts_blocks") or []):
        if not isinstance(b, dict) or not b.get("text"):
            continue
        blk = {"text": _sanitize_block_text(b["text"]),
               "pause_ms": max(0, min(2000, int(b.get("pause_ms", 300) or 0)))}
        if b.get("stability") is not None:
            blk["stability"] = max(0.0, min(1.0, float(b["stability"])))
        if b.get("style") is not None:
            blk["style"] = max(0.0, min(1.0, float(b["style"])))
        if b.get("type"):
            blk["type"] = b["type"]
        blocks.append(blk)
    if blocks:
        enriched["tts_blocks"] = blocks

    # Back-compat: also merge per-segment tts_text if the LLM provided it.
    tts_by_id = {s["id"]: s.get("tts_text") for s in (data.get("segments") or [])
                 if isinstance(s, dict) and s.get("id") and s.get("tts_text")}
    for seg in enriched.get("segments", []):
        if seg["id"] in tts_by_id:
            seg["tts_text"] = _sanitize_tts(tts_by_id[seg["id"]])

    meta["key_points"] = len(kps)
    meta["tts_blocks"] = len(blocks)
    return enriched, meta


def _sanitize_block_text(text):
    """V2 block-text cleaner: KEEPS native <break> tags (they are intentional in-block
    pacing in chunk-and-stitch V2), but normalizes them: collapse stacked breaks, cap
    duration at 2.0s. Keeps CAPS emphasis. Used for grouped blocks where the model
    reads ahead across the break (preserving the emotional arc)."""
    if not text:
        return text
    # collapse consecutive breaks into one
    text = re.sub(r'(<break[^>]*/>\s*){2,}', lambda m: '<break time="1.0s" /> ', text)
    # cap break duration at 2.0s
    text = re.sub(r'<break\s+time="([\d.]+)s"\s*/>',
                  lambda m: f'<break time="{min(2.0, float(m.group(1))):.1f}s" />', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _sanitize_tts(text):
    """Programmatic TTS pre-processing (system pillars B & C). Ensures predictable
    pacing without manual babysitting:
      - Remove <break> tags (distort prosody).
      - PILLAR B (newline limit): collapse 3+ newlines to exactly 2.
      - PILLAR B (list protection): a sentence that ends a comma-list (e.g.
        '...A, B, and C.') followed by a paragraph break makes ElevenLabs think the
        scene ended and DRAG the final list words. Replace that '.\\n\\n' with an
        em-dash bridge '— ' to keep momentum into the next thought.
      - PILLAR C (anchor-word caps): caps are the emphasis mechanism (safe at locked
        style 0.0). We keep caps as-is.
      - Normalize ellipsis runs; tidy spaces (preserve paragraph breaks)."""
    if not text:
        return text
    # break tags
    text = re.sub(r'([.!?])\s*<break[^>]*/>\s*', r'\1.. ', text)
    text = re.sub(r'\s*<break[^>]*/>\s*', ' ', text)
    # collapse 3+ newlines to exactly two
    text = re.sub(r'\n{3,}', '\n\n', text)
    # list-protection: ", and <word>." or ", <word>, and <word>." immediately before \n\n
    # → bridge with em-dash so the AI doesn't drag the closing list item.
    text = re.sub(r'(,\s+(?:and\s+)?[A-Za-z][\w\s]{0,30})\.\s*\n\n', r'\1 — ', text)
    # normalize ellipses, tidy inline spaces (keep newlines)
    text = re.sub(r'\.{2,}', '...', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def preprocess_tts(text):
    """Public alias for the programmatic TTS cleaner (system pillar B)."""
    return _sanitize_tts(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Optimize a script for takeaway emphasis.")
    ap.add_argument("script")
    ap.add_argument("--output")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="Use deterministic fallback only")
    args = ap.parse_args(argv)

    script = json.loads(Path(args.script).read_text())
    enriched, meta = optimize(script, dry_run=args.dry_run, use_llm=not args.no_llm)
    print(f"  optimize: source={meta.get('source')} key_points={meta.get('key_points', 0)}")
    if meta.get("llm_error"):
        print(f"  (LLM unavailable, used fallback: {meta['llm_error'][:80]})")
    for kp in enriched.get("key_points", []):
        e = kp["emphasis"]
        print(f"    [{e['treatment']}] {kp['text'][:55]}")
    if args.dry_run:
        return 0
    out = args.output or args.script
    Path(out).write_text(json.dumps(enriched, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
