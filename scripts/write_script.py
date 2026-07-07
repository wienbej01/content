#!/usr/bin/env python3
"""write_script.py — LLM script writer (format-aware, source-grounded, revision-capable).

Writes (or revises) a script from a research brief + the brand bibles, honouring the FORMAT
as a hard constraint (a 3-min short is written as a short). The AUTHOR in the script-stage
feedback loop: write → review → revise(fixes) → re-review. Returns (script_dict, prompt).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
CU = ROOT / "docs" / "channel_universe"
SCRIPT_BIBLES = ["JAMES_CHARACTER_BIBLE.md", "UNIVERSE_BIBLE.md", "FORBIDDEN_PATTERNS.md"]


def _bibles(max_each=5000):
    out = []
    for b in SCRIPT_BIBLES:
        f = CU / b
        if f.exists():
            out.append(f"===== {b} =====\n{f.read_text(errors='replace')[:max_each]}")
    return "\n\n".join(out)


RESEARCH_TEXT_CAP = 8000
ANTI_FABRICATION_RULE = (
    "Do NOT name a researcher, institution, study, statistic, percentage, or date "
    "UNLESS it appears verbatim in the SOURCE RESEARCH TEXT or the sourced claims below. "
    "If you cannot find a specific finding in the provided material, make the point "
    "WITHOUT a fabricated citation — use a general observation, not a named study. "
    "It is better to make fewer, fully-grounded claims than to pad with invented research. "
    "An unsourced named-study claim is a HARD FAILURE that will be rejected."
)

CLAIM_STRENGTH_RULE = (
    "MATCH THE SOURCE'S CLAIM STRENGTH — never upgrade it. "
    "An observation stays an observation; a quote stays a quote; a single study stays 'one study'; "
    "a commentary stays a commentary. Do NOT turn a quote or opinion into a 'finding', a 'study', "
    "or a 'warning'. Do NOT turn a single trial into settled science. "
    "ATTRIBUTE EXACTLY: cite the actual authors/source as the source frames it. If a paper is by "
    "named authors and an institution only COMMENTS on it, attribute to the authors (e.g. "
    "'Shrestha and colleagues (2019)'), NOT to the commenting institution. "
    "Use hedged language that matches the evidence: 'an observation', 'early evidence suggests', "
    "'one trial reported', 'a commentary argues' — not 'research proves' or 'studies show' unless the "
    "source itself is that strong. Over-claiming a real source's strength is a HARD FAILURE."
)


def build_writer_prompt(brief, video_type, prior_script=None, fixes=None):
    from episode_format import format_block, get_format
    _fmt = get_format(video_type)
    research_text = brief.get("research_text", "")[:RESEARCH_TEXT_CAP]
    claims_json = json.dumps(brief.get("key_claims", []), indent=2)
    sources_json = json.dumps(brief.get("sources", []), indent=2)
    word_lo, word_hi = _fmt["word_range"]
    base = f"""You are the SCRIPT WRITER for Leverage Mind (host: James Harrington — ~60yo British,
RP, calm, measured, lightly contrarian; no hype). Write a script that obeys the FORMAT as a
HARD CONSTRAINT and grounds EVERY factual claim in the SOURCE RESEARCH TEXT or the sourced
claims below (never invent or mis-attribute a statistic/study/date — sourcing is a legal
non-negotiable).

=== ANTI-FABRICATION RULE (HARD CONSTRAINT) ===
{ANTI_FABRICATION_RULE}

=== CLAIM-STRENGTH RULE (HARD CONSTRAINT) ===
{CLAIM_STRENGTH_RULE}

{format_block(video_type)}

WORD BUDGET (HARD CONSTRAINT): Your script MUST contain {word_lo}-{word_hi} words total.
Count your words across ALL segments before returning. A script outside this range
is non-compliant and will be rejected regardless of creative quality.
Target: ~{_fmt['target_sec']}s of spoken narration at James's measured pace.

CRAFT (retention): open with a 3-second open loop that delivers the title promise; keep a
reason to stay; make the takeaway save-worthy (concrete) and the piece share-worthy (it must
make the viewer FEEL something); close with a specific CTA (a real next action / a binary
engagement question), never "in conclusion".

OUTPUT — return ONLY JSON:
{{
  "project_id": "<slug>", "title": "<emotional, curiosity-driven, <=70 chars>",
  "video_type": "{video_type}", "narration_mode": "continuous_voiceover",
  "segments": [{{"id": "001_hook", "audio_mode": "generated_tts", "text": "<spoken words>"}}, ...],
  "key_points": [{{"text": "<the exact takeaway sentence the video builds to>"}}],
  "sources": [{{"id": "...", "citation": "...", "url": "...", "claims_used": ["..."]}}]
}}

=== SOURCE RESEARCH TEXT (every factual claim MUST trace to THIS text or the sourced claims below) ===
{research_text}

=== SOURCED CLAIMS ===
{claims_json}

=== SOURCES ===
{sources_json}

BRAND BIBLES (voice + forbidden patterns):
{_bibles()}
"""
    if prior_script and fixes:
        base += f"""

=== REVISION TASK (HARD CONSTRAINT) ===
This is a REVISION. Incorporate EVERY reviewer fix while staying within the FORMAT word budget.
HARD CONSTRAINT: The FINAL output MUST have [{word_lo},{word_hi}] words total. Count your words and verify
before returning. Do NOT expand beyond {word_hi} — adapt every fix to fit within the budget.
If you must cut material to stay within [{word_lo},{word_hi}] words, reduce the least essential
points while preserving the core hook, proof, and takeaway.

PRIOR SCRIPT:
{json.dumps(prior_script, indent=2)}

REVIEWER FIXES TO INCORPORATE:
{json.dumps(fixes, indent=2)}
"""
    return base


def detect_unsourced_named_claims(script_text, brief):
    """Heuristic: flag named-source phrases in script not found in brief material.

    Returns a list of suspicious phrases (WARNING-level diagnostics, not a hard gate).
    """
    import re
    # Build corpus of sourced material to check against
    corpus = brief.get("research_text", "").lower()
    for claim in brief.get("key_claims", []):
        if isinstance(claim, dict):
            corpus += " " + json.dumps(claim).lower()
        else:
            corpus += " " + str(claim).lower()
    for src in brief.get("sources", []):
        corpus += " " + json.dumps(src).lower()

    # Extract candidate named-source phrases: capitalized words near claim verbs/keywords
    trigger = r'(?:stud(?:y|ies)|research(?:ers)?|found|paper|university|institute|journal|professor|published)'
    # Pattern: Capitalized multi-word name (2+ caps words) near a trigger
    pattern = re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:University|Institute|School|GSB|MIT|Lab))?)\s+' + trigger
        + r'|' + trigger + r'\s+(?:at|by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        re.MULTILINE
    )
    # Also catch: "a YYYY study/paper by Name" or "Name (YYYY)"
    year_pattern = re.compile(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)'
        r'|(\d{4})\s+(?:study|paper|research)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    )

    flagged = []
    for m in pattern.finditer(script_text):
        name = (m.group(1) or m.group(2)).strip()
        if name.lower() not in corpus:
            flagged.append(name)
    for m in year_pattern.finditer(script_text):
        name = (m.group(1) or m.group(4) or "").strip()
        if name and name.lower() not in corpus:
            flagged.append(name)

    return list(dict.fromkeys(flagged))  # deduplicate preserving order


def detect_overclaim_language(script_text, brief):
    """Heuristic: flag when script uses strong evidentiary language for a weakly-framed source.

    Returns a list of warning strings. WARNING-level only — not a hard gate.
    """
    import re

    # Build a mapping: lowered source name → framing words from brief
    weak_framings = {'quote', 'observation', 'commentary', 'opinion', 'argues',
                     'suggests', 'notes', 'remarks', 'speculates', 'proposes'}
    strong_verbs = re.compile(
        r'\b(?:found|proved|demonstrates?|research\s+shows?|study\s+found|'
        r'RCT\s+found|studies\s+show|research\s+proves?|established)\b', re.IGNORECASE
    )

    # Extract source names and their framing from brief material
    corpus_text = brief.get("research_text", "")
    claims_text = " ".join(
        (c.get("claim", "") if isinstance(c, dict) else str(c))
        for c in brief.get("key_claims", [])
    )
    brief_combined = (corpus_text + " " + claims_text).lower()

    # Find named entities in script near strong verbs
    # Split script into rough segments (sentences)
    sentences = re.split(r'[.!?]+', script_text)
    warnings = []

    # Extract capitalized name phrases from each sentence
    name_pat = re.compile(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*')

    for sent in sentences:
        if not strong_verbs.search(sent):
            continue
        names = name_pat.findall(sent)
        for name in names:
            nl = name.lower()
            # Check if this name appears in brief material
            if nl not in brief_combined:
                continue
            # Check if brief frames this source weakly
            # Look for weak framing words near the name in the brief
            # Find a window around the name in brief_combined
            idx = brief_combined.find(nl)
            if idx == -1:
                continue
            window = brief_combined[max(0, idx - 80):idx + len(nl) + 80]
            if any(w in window for w in weak_framings):
                warnings.append(
                    f"Possible over-claim: '{name}' framed weakly in brief "
                    f"but script uses strong evidentiary language in: "
                    f"'{sent.strip()[:80]}...'"
                )
                break  # one warning per sentence

    return list(dict.fromkeys(warnings))


def check_unsourced_named_claims(script_text, brief, mode="warn"):
    """Check for unsourced named claims. In 'warn' mode, returns warnings.
    In 'block' mode, returns a dict with 'blocked' flag and details."""
    flagged = detect_unsourced_named_claims(script_text, brief)
    if not flagged:
        return {"blocked": False, "claims": []}
    if mode == "block":
        return {
            "blocked": True,
            "claims": flagged,
            "error": f"BLOCKED_UNSOURCED_NAMED_CLAIM: {', '.join(flagged)}"
        }
    return {"blocked": False, "claims": flagged}


def write_script(brief, video_type, prior_script=None, fixes=None, dry_run=False):
    prompt = build_writer_prompt(brief, video_type, prior_script, fixes)
    if dry_run:
        return None, prompt
    from llm_call import llm_call
    data, raw, _, _ = llm_call(task="script_writing", prompt=prompt,
                               model_profile="sonnet_creative", expect_json=True, timeout=240)
    if isinstance(data, list):
        data = data[0] if data else {}
    if isinstance(data, dict):
        data.setdefault("video_type", video_type)
        data.setdefault("narration_mode", "continuous_voiceover")

    script_text = " ".join(
        seg.get("text", "") for seg in (data or {}).get("segments", [])
    )
    unsourced_mode = os.environ.get("UNSOURCED_CLAIM_MODE", "warn")
    unsourced = check_unsourced_named_claims(script_text, brief, mode=unsourced_mode)
    if unsourced["blocked"]:
        print(f"  BLOCKED [unsourced named claim]: {unsourced['error']}", file=sys.stderr)
        return None, prompt
    if unsourced["claims"]:
        print(f"  WARNING [fabrication heuristic]: possibly unsourced claims: {unsourced['claims']}",
              file=sys.stderr)

    overclaim_warnings = detect_overclaim_language(script_text, brief)
    if overclaim_warnings:
        print(f"  WARNING [overclaim heuristic]: {overclaim_warnings}",
              file=sys.stderr)

    return data, prompt


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("brief_json")
    ap.add_argument("--format", dest="video_type", default="short")
    ap.add_argument("--output")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    brief = json.loads(Path(args.brief_json).read_text())
    data, prompt = write_script(brief, args.video_type, dry_run=args.dry_run)
    if args.dry_run:
        print(f"  DRY RUN — writer prompt {len(prompt)} chars ({args.video_type})")
        return 0
    print(f"  script: {data.get('title')!r} ({len(data.get('segments', []))} segments)")
    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
