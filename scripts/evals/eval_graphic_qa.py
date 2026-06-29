#!/usr/bin/env python3
"""eval_graphic_qa.py — Graphic semantic alignment validation (S16_T004).

Evaluates graphic title/template/content vs beat narration for semantic alignment.
Validates that graphics are not black title cards and are topic-aligned with narration.

Pass criteria:
- Black title card fails (no semantic content)
- Topic-misaligned graphic fails
- Aligned 3-step framework passes
- Professional graphic templates with meaningful content pass

Usage:
  python3 scripts/evals/eval_graphic_qa.py --production-id <id> --out <json>
"""
import argparse
import json
import re
import sys
from pathlib import Path


# Black title card patterns (no semantic value)
BLACK_TITLE_PATTERNS = [
    r"^title\s*$",
    r"^intro\s*$",
    r"^chapter\s+\d+\s*$",
    r"^part\s+\d+\s*$",
    r"^section\s+\d+\s*$",
    r"^\s*$",  # Empty or whitespace only
    r"^placeholder\s*$",
    r"^tbc\s*$",
    r"^todo\s*$",
]

# Weak title patterns (minimal semantic value)
WEAK_TITLE_PATTERNS = [
    r"^slide\s+\d+\s*$",
    r"^screen\s+\d+\s*$",
    r"^graphic\s+\d+\s*$",
    r"^image\s+\d+\s*$",
    r"^fig\s+\d+\s*$",
]


def is_black_title_card(text: str) -> bool:
    """Check if text is a black title card (no semantic value)."""
    if not text or not text.strip():
        return True

    t = text.strip().lower()
    for pattern in BLACK_TITLE_PATTERNS:
        if re.match(pattern, t, re.IGNORECASE):
            return True
    return False


def is_weak_title(text: str) -> bool:
    """Check if text is a weak title (minimal semantic value)."""
    if not text or not text.strip():
        return True

    t = text.strip().lower()
    for pattern in WEAK_TITLE_PATTERNS:
        if re.match(pattern, t, re.IGNORECASE):
            return True
    return False


def extract_keywords_from_text(text: str) -> set:
    """Extract meaningful keywords from text for semantic comparison."""
    if not text:
        return set()

    # Remove common stop words
    stop_words = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "can", "this",
        "that", "these", "those", "i", "you", "we", "they", "it", "its"
    }

    # Extract words (3+ characters)
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {w for w in words if w not in stop_words}


def compute_semantic_overlap(text1: str, text2: str) -> float:
    """Compute semantic overlap between two texts (Jaccard similarity)."""
    keywords1 = extract_keywords_from_text(text1)
    keywords2 = extract_keywords_from_text(text2)

    if not keywords1 and not keywords2:
        return 0.0

    if not keywords1 or not keywords2:
        return 0.0

    intersection = keywords1 & keywords2
    union = keywords1 | keywords2

    return len(intersection) / len(union) if union else 0.0


def check_3step_framework_alignment(dts: dict, narration: str) -> dict:
    """Check if 3-step framework content aligns with narration."""
    if dts.get("template_type") != "framework_3_step":
        return {"applicable": False}

    content = dts.get("content", {})
    title = content.get("title", "")
    steps = content.get("steps", [])

    if not steps or len(steps) != 3:
        return {
            "applicable": True,
            "aligned": False,
            "reason": "framework_3_step must have exactly 3 steps"
        }

    # Extract keywords from title and steps
    framework_keywords = set()
    framework_keywords.update(extract_keywords_from_text(title))
    for step in steps:
        framework_keywords.update(extract_keywords_from_text(step.get("label", "")))
        framework_keywords.update(extract_keywords_from_text(step.get("description", "")))

    narration_keywords = extract_keywords_from_text(narration)

    if not framework_keywords:
        return {
            "applicable": True,
            "aligned": False,
            "reason": "framework has no meaningful keywords"
        }

    overlap = len(framework_keywords & narration_keywords)
    overlap_ratio = overlap / len(framework_keywords) if framework_keywords else 0.0

    # Require at least 20% keyword overlap
    aligned = overlap_ratio >= 0.20

    return {
        "applicable": True,
        "aligned": aligned,
        "overlap_count": overlap,
        "framework_keyword_count": len(framework_keywords),
        "narration_keyword_count": len(narration_keywords),
        "overlap_ratio": round(overlap_ratio, 3),
        "reason": "aligned" if aligned else f"insufficient semantic overlap ({overlap_ratio:.1%})"
    }


def eval_graphic_unit(ru: dict, beat_narration: str = "") -> dict:
    """Evaluate one local graphic unit for semantic alignment."""

    # Get deterministic text spec
    meta = json.loads(ru.get("metadata_json") or "{}")
    dts = meta.get("deterministic_text_spec", {})

    # Get text content
    text = ""
    if isinstance(dts, dict):
        text = dts.get("text") or dts.get("headline") or dts.get("quote") or ""

    # Check for black title card
    is_black = is_black_title_card(text)
    is_weak = is_weak_title(text) if not is_black else False

    # Get template type if available
    template_type = dts.get("template_type", "unknown")

    # Check 3-step framework alignment if applicable
    framework_check = check_3step_framework_alignment(dts, beat_narration)

    # Compute semantic overlap with narration
    semantic_overlap = 0.0
    if beat_narration and text:
        semantic_overlap = compute_semantic_overlap(text, beat_narration)

    # Determine overall alignment
    if is_black:
        alignment = "fail"
        alignment_reason = "BLOCKED_GRAPHIC_IS_BLACK_TITLE_CARD: No semantic content"
    elif template_type == "framework_3_step" and framework_check.get("applicable"):
        if framework_check.get("aligned"):
            alignment = "pass"
            alignment_reason = "framework_3_step semantically aligned with narration"
        else:
            alignment = "fail"
            alignment_reason = f"BLOCKED_GRAPHIC_MISALIGNED: {framework_check.get('reason')}"
    elif semantic_overlap < 0.1 and beat_narration:
        alignment = "fail"
        alignment_reason = f"BLOCKED_GRAPHIC_MISALIGNED: Insufficient semantic overlap ({semantic_overlap:.1%})"
    elif is_weak:
        alignment = "warn"
        alignment_reason = "weak title (minimal semantic value)"
    else:
        alignment = "pass"
        alignment_reason = "graphic has meaningful semantic content"

    return {
        "graphic_id": ru["id"],
        "label": ru.get("label", ""),
        "ordinal": ru.get("ordinal", 0),
        "template_type": template_type,
        "text": text if text else "",
        "duration_sec": round(ru.get("required_duration_ms", 0) / 1000.0, 3),
        "is_black_title_card": is_black,
        "is_weak_title": is_weak,
        "semantic_overlap": round(semantic_overlap, 3),
        "framework_alignment": framework_check,
        "alignment": alignment,
        "alignment_reason": alignment_reason,
    }


def eval_production(production_id: str, db_path: str = None, beat_narrations: dict = None) -> dict:
    """Evaluate semantic alignment for all local graphic units."""
    import sqlite3
    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    units = conn.execute("""
        SELECT ru.id, ru.label, ru.required_duration_ms,
               ru.required_start_ms, ru.required_end_ms, ru.metadata_json,
               ru.ordinal
        FROM render_units ru
        WHERE ru.production_id=? AND ru.asset_type='local_graphic'
          AND ru.status NOT IN ('stale', 'cancelled')
        ORDER BY ru.ordinal
    """, (production_id,)).fetchall()

    conn.close()

    if not units:
        return {"production_id": production_id, "graphics": [], "status": "pass",
                "count": 0, "note": "no local graphic units"}

    results = []
    for u in units:
        ru = dict(u)

        # Get beat narration if provided
        narration = ""
        if beat_narrations:
            narration = beat_narrations.get(ru.get("label", ""), "")

        results.append(eval_graphic_unit(ru, narration))

    fail_count = sum(1 for r in results if r["alignment"] == "fail")
    warn_count = sum(1 for r in results if r["alignment"] == "warn")
    black_count = sum(1 for r in results if r["is_black_title_card"])

    if fail_count > 0:
        status = "fail"
    elif warn_count > 0:
        status = "warn"
    else:
        status = "pass"

    return {
        "production_id": production_id,
        "count": len(results),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "black_title_count": black_count,
        "status": status,
        "graphics": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Graphic semantic alignment evaluation")
    ap.add_argument("--production-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db-path", default=None)
    ap.add_argument("--beat-narrations", type=Path, help="JSON file mapping beat labels to narrations")
    args = ap.parse_args(argv)

    # Load beat narrations if provided
    narrations = {}
    if args.beat_narrations and args.beat_narrations.exists():
        narrations = json.loads(args.beat_narrations.read_text())

    result = eval_production(args.production_id, db_path=args.db_path, beat_narrations=narrations)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Graphic semantic alignment eval for {result['production_id']}:")
    print(f"  Graphics: {result['count']}, Fail: {result['fail_count']}, Warn: {result['warn_count']}")
    print(f"  Black titles: {result['black_title_count']}, Status: {result['status']}")
    for r in result.get("graphics", []):
        print(f"  [{r['label']}] {r['template_type']:20s} "
              f"align={r['alignment']:5s} black={r['is_black_title_card']} "
              f"overlap={r['semantic_overlap']:.2f}")
        if r["alignment"] == "fail":
            print(f"    → BLOCKED: {r['alignment_reason']}")

    return 0 if result["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
