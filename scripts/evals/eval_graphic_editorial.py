#!/usr/bin/env python3
"""Graphic editorial quality report eval.

Analyzes local graphic units for editorial value, not just render correctness.
Deterministic heuristics (no LLM call required).

Usage:
  python3 scripts/evals/eval_graphic_editorial.py --production-id <id> --out <json>
"""
import argparse
import json
import sys
from pathlib import Path


MIN_READ_TIME_MS = 1500  # minimum ms to read any text
CHARS_PER_SECOND = 15    # reading speed: ~15 chars/s for title cards


def classify_editorial_role(text: str, duration_ms: int) -> str:
    """Classify editorial role based on text content and duration."""
    if not text or not text.strip():
        return "missing"
    t = text.strip().upper()
    if any(kw in t for kw in ["SUMMARY", "KEY POINTS", "RECAP", "TL;DR"]):
        return "summary"
    if any(kw in t for kw in ["COMING UP", "NEXT", "UP NEXT", "WHAT'S NEXT"]):
        return "transition"
    if any(kw in t for kw in ["VS", "VERSUS", "COMPARE", "CONTRAST"]):
        return "contrast"
    if any(kw in t for kw in ["COSTS", "PRICE", "$", "DAMAGE", "IMPACT"]):
        return "callout"
    return "setup"


def analyze_text_quality(text: str) -> dict:
    """Analyze text for editorial quality."""
    if not text or not text.strip():
        return {
            "text_empty": True,
            "word_count": 0,
            "char_count": 0,
            "is_complete_thought": False,
            "has_capitalization": False,
        }
    t = text.strip()
    words = t.split()
    return {
        "text_empty": False,
        "word_count": len(words),
        "char_count": len(t),
        "is_complete_thought": len(words) >= 3,
        "has_capitalization": any(c.isupper() for c in t[:20]),
    }


def analyze_duration(text: str, duration_ms: int) -> dict:
    """Analyze if duration is appropriate for the text."""
    if not text or not text.strip():
        return {
            "duration_ms": duration_ms,
            "duration_readable": False,
            "duration_too_short": duration_ms < MIN_READ_TIME_MS,
            "duration_too_long": duration_ms > 8000,
            "recommendation": "empty_text_no_duration_needed",
        }
    t = text.strip()
    needed_ms = max(MIN_READ_TIME_MS, len(t) / CHARS_PER_SECOND * 1000)
    return {
        "duration_ms": duration_ms,
        "duration_readable": duration_ms >= needed_ms,
        "duration_too_short": duration_ms < needed_ms,
        "duration_too_long": duration_ms > max(needed_ms * 3, 8000),
        "min_read_time_ms": int(needed_ms),
        "recommendation": "ok" if duration_ms >= needed_ms else f"needs_{int(needed_ms)}ms",
    }


def eval_unit(ru: dict, dts: dict) -> dict:
    """Evaluate one local graphic unit."""
    text = ""
    if isinstance(dts, dict):
        text = dts.get("text") or dts.get("headline") or ""

    dur = ru.get("required_duration_ms", 0) or 0
    label = ru.get("label", "")

    editorial_role = classify_editorial_role(text, dur)
    text_quality = analyze_text_quality(text)
    duration_analysis = analyze_duration(text, dur)

    is_weak = (
        text_quality["text_empty"] or
        duration_analysis["duration_too_short"] or
        duration_analysis["duration_too_long"]
    )

    return {
        "graphic_id": ru["id"],
        "label": label,
        "ordinal": ru.get("ordinal", 0),
        "text": text if text else "",
        "duration_sec": round(dur / 1000.0, 3) if dur else 0,
        "duration_ms": dur,
        "editorial_role": editorial_role,
        "is_complete_thought": text_quality["is_complete_thought"],
        "has_capitalization": text_quality["has_capitalization"],
        "text_empty": text_quality["text_empty"],
        "duration_too_short": duration_analysis["duration_too_short"],
        "duration_too_long": duration_analysis["duration_too_long"],
        "is_weak": is_weak,
        "recommended_revision": _suggest_revision(editorial_role, text_quality, dur),
    }


def _suggest_revision(role: str, tq: dict, dur: int) -> str:
    """Suggest a revision based on findings."""
    if tq["text_empty"]:
        return "add descriptive text to title card"
    if dur < 1500:
        return f"extend duration from {dur}ms to at least 1500ms"
    if not tq["is_complete_thought"]:
        return "expand to a complete phrase (3+ words)"
    return ""


def eval_production(production_id: str, db_path: str = None) -> dict:
    """Evaluate editorial quality for all local graphic units."""
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
        meta = json.loads(ru.get("metadata_json") or "{}")
        dts = meta.get("deterministic_text_spec", {})
        results.append(eval_unit(ru, dts))

    weak_count = sum(1 for r in results if r["is_weak"])
    empty_text_count = sum(1 for r in results if r["text_empty"])

    if weak_count > 0:
        status = "fail"
    elif empty_text_count > 0:
        status = "warn"
    else:
        status = "pass"

    return {
        "production_id": production_id,
        "count": len(results),
        "weak_count": weak_count,
        "empty_text_count": empty_text_count,
        "status": status,
        "graphics": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Graphic editorial quality eval")
    ap.add_argument("--production-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = eval_production(args.production_id, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Graphic editorial eval for {result['production_id']}:")
    print(f"  Graphics: {result['count']}, Weak: {result['weak_count']}")
    print(f"  Empty text: {result['empty_text_count']}, Status: {result['status']}")
    for r in result.get("graphics", []):
        print(f"  [{r['label']}] role={r['editorial_role']:10s} "
              f"dur={r['duration_ms']:>5}ms text_empty={r['text_empty']} "
              f"weak={r['is_weak']}")
        if r["recommended_revision"]:
            print(f"    → {r['recommended_revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
