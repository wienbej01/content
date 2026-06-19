#!/usr/bin/env python3
"""episode_format.py — format profiles + the FORMAT block injected into EVERY prompt.

The format is a HARD INPUT. A "3-minute short" must be authored AND reviewed by short
standards (one sharp insight, fast, punchy) — never judged against a flagship's
depth/length expectations. Authors and all reviewers receive this block so they hold
the artifact to the RIGHT bar.
"""

FORMAT_PROFILES = {
    "short": {
        "label": "3-minute SHORT",
        "target_sec": 180,
        "target_sec_range": [120, 200],
        "word_range": [280, 460],
        "structure": "ONE sharp idea: hook (open loop in 3s) → one vivid proof/mechanism "
                     "→ one memorable takeaway → tight CTA. NO multi-part framework, NO "
                     "deep elaboration — depth is NOT expected or wanted at this length.",
        "review_note": "Judge as a SHORT. Do NOT penalise it for lacking a multi-step "
                       "framework or 4-6 minutes of depth — that is WRONG for this format. "
                       "A short wins on a single surprising, save-worthy, shareable idea "
                       "delivered fast. Length adequacy = within the word range above.",
    },
    "explainer": {
        "label": "6-10 minute EXPLAINER",
        "target_sec": 480,
        "target_sec_range": [360, 720],
        "word_range": [1400, 2600],
        "structure": "hook → promise → 3-5 part original framework → worked example → "
                     "takeaway → CTA.",
        "review_note": "Judge as a full explainer: an original multi-part framework and "
                       "depth ARE expected.",
    },
    "teaser": {
        "label": "60-90s TEASER",
        "target_sec": 75,
        "target_sec_range": [50, 100],
        "word_range": [140, 230],
        "structure": "intrigue → promise of the series/topic → CTA. No framework.",
        "review_note": "Judge as a teaser: intrigue + promise, not depth.",
    },
}


def get_format(video_type):
    return FORMAT_PROFILES.get(video_type, FORMAT_PROFILES["explainer"])


def format_block(video_type):
    """The text injected into every author + reviewer prompt so the bar matches the format."""
    f = get_format(video_type)
    return (
        f"=== FORMAT (HARD CONSTRAINT — hold the work to THIS bar, not another) ===\n"
        f"FORMAT: {f['label']}\n"
        f"Target duration: ~{f['target_sec']}s (acceptable {f['target_sec_range'][0]}-"
        f"{f['target_sec_range'][1]}s)\n"
        f"Word budget: {f['word_range'][0]}-{f['word_range'][1]} words\n"
        f"Structure: {f['structure']}\n"
        f"REVIEW NOTE: {f['review_note']}\n"
    )


def count_script_words(script_payload: dict) -> int:
    """Total spoken words across all segments — a real count, not an estimate.

    Each segment may carry an explicit ``word_count``; otherwise the words are
    counted from ``text`` (mirroring authoring_service.save_script, which stores
    ``word_count or len(text.split())``).
    """
    total = 0
    for seg in (script_payload or {}).get("segments", []):
        wc = seg.get("word_count")
        if wc is None:
            wc = len((seg.get("text") or "").split())
        total += int(wc)
    return total


def script_within_budget(script_payload: dict, video_type: str) -> bool:
    """True iff the script's total words fall inside the format's word budget.

    The word budget is the duration budget expressed in words — it is exactly what
    ``format_block`` tells the writer ("Word budget: lo-hi words"), so enforcing it
    is a real check of the delivered script against the format spec. No estimated
    speaking rate is hard-coded: the James ElevenLabs voice measures ~138 wpm on
    the clean s9_paid sample (70 words -> 30.35s) but only ~74-108 wpm on the longer
    ai_notes_teaser narration, i.e. the pace varies, so a fixed words-per-minute
    constant would be unsound. The format's own word_range (calibrated against
    target_sec_range) is the authoritative budget.
    """
    f = get_format(video_type)
    lo, hi = f["word_range"]
    return lo <= count_script_words(script_payload) <= hi

