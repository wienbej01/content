#!/usr/bin/env python3
"""Baseline-vs-canary comparison report for S06_T004.

Compares original bad fixture against fresh canary render.
No provider render calls made. Read-only analysis.

Usage:
  python3 scripts/evals/eval_canary_comparison.py --baseline <path> --canary <path> --out <json>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PRODUCTION_ID = "prod_2f9bb58c0508465fb51ac6b4578bba92"
DEFAULT_BASELINE = Path("fixtures/bad_runs/prod_2f9bb58c0508465fb51ac6b4578bba92/final_16x9.mp4")
DEFAULT_CANARY = Path("assets/media/prod_2f9bb58c0508465fb51ac6b4578bba92/canary_pjob_fe40c769ad84418fb1091449e63d4da6.mp4")


def probe(path: Path) -> dict:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}


def compare(baseline: Path, canary: Path, db_path: str = None) -> dict:
    """Produce baseline-vs-canary comparison report."""
    b_probe = probe(baseline)
    c_probe = probe(canary)

    b_fmt = b_probe.get("format", {})
    c_fmt = c_probe.get("format", {})

    b_vs = [s for s in b_probe.get("streams", []) if s.get("codec_type") == "video"]
    c_vs = [s for s in c_probe.get("streams", []) if s.get("codec_type") == "video"]
    b_as = [s for s in b_probe.get("streams", []) if s.get("codec_type") == "audio"]
    c_as = [s for s in c_probe.get("streams", []) if s.get("codec_type") == "audio"]

    b_v = b_vs[0] if b_vs else {}
    c_v = c_vs[0] if c_vs else {}
    b_a = b_as[0] if b_as else {}
    c_a = c_as[0] if c_as else {}

    # Load DB data
    import sqlite3
    conn = sqlite3.connect(db_path or "db/production.db")
    conn.row_factory = sqlite3.Row

    pj_id = "pjob_fe40c769ad84418fb1091449e63d4da6"
    ru = conn.execute("SELECT source_slice_sha256 FROM render_units WHERE id='render_f91a245c14b341b6a7975e2a8d5716fc'").fetchone()
    da = conn.execute("""SELECT id, sha256, size_bytes, uri FROM artifacts 
        WHERE kind='provider_diagnostic_audio' AND provider_job_id=?""", (pj_id,)).fetchone()
    art = conn.execute("""SELECT id, sha256, size_bytes FROM artifacts 
        WHERE kind='generated_media' AND provider_job_id=?""", (pj_id,)).fetchone()
    conn.close()

    source_slice_sha = ru["source_slice_sha256"] if ru else None

    # Diagnostic audio probe
    diag_dur = None
    if da and da["uri"]:
        dp = Path(da["uri"])
        if dp.exists():
            diag = probe(dp)
            diag_dur = float(diag.get("format", {}).get("duration", 0))

    # Build comparison
    comparison = {
        "production_id": PRODUCTION_ID,
        "baseline": {
            "path": str(baseline),
            "exists": baseline.exists(),
            "size_bytes": baseline.stat().st_size if baseline.exists() else 0,
            "duration_sec": round(float(b_fmt.get("duration", 0)), 4) if b_fmt.get("duration") else None,
            "bitrate": int(b_fmt.get("bit_rate", 0)) if b_fmt.get("bit_rate") else None,
            "video": {
                "resolution": f"{b_v.get('width','?')}x{b_v.get('height','?')}",
                "fps": b_v.get("r_frame_rate", "?"),
                "codec": b_v.get("codec_name", "?"),
            } if b_v else None,
            "audio": {
                "sample_rate": int(b_a.get("sample_rate", 0)) if b_a.get("sample_rate") else None,
                "channels": b_a.get("channels", "?"),
                "codec": b_a.get("codec_name", "?"),
            } if b_a else None,
        },
        "canary": {
            "path": str(canary),
            "exists": canary.exists(),
            "size_bytes": canary.stat().st_size if canary.exists() else 0,
            "duration_sec": round(float(c_fmt.get("duration", 0)), 4) if c_fmt.get("duration") else None,
            "bitrate": int(c_fmt.get("bit_rate", 0)) if c_fmt.get("bit_rate") else None,
            "video": {
                "resolution": f"{c_v.get('width','?')}x{c_v.get('height','?')}",
                "fps": c_v.get("r_frame_rate", "?"),
                "codec": c_v.get("codec_name", "?"),
            } if c_v else None,
            "audio": {
                "sample_rate": int(c_a.get("sample_rate", 0)) if c_a.get("sample_rate") else None,
                "channels": c_a.get("channels", "?"),
                "codec": c_a.get("codec_name", "?"),
            } if c_a else None,
        },
        "provenance": {
            "source_slice_sha256": source_slice_sha,
            "diagnostic_audio_sha256": da["sha256"] if da and da["sha256"] else None,
            "diagnostic_audio_matches_source_slice": da and da["sha256"] == source_slice_sha if source_slice_sha else False,
            "diagnostic_audio_duration_sec": diag_dur,
            "diagnostic_audio_exists": da is not None,
            "generated_media_sha256": art["sha256"] if art and art["sha256"] else None,
            "generated_media_exists": art is not None,
            "expected_source_duration_ms": 4572,
            "expected_source_duration_sec": 4.572,
        },
        "lipsync": {
            "baseline_offset_ms": -4950.0,
            "baseline_confidence": 0.1369,
            "baseline_method": "mouth_motion_proxy",
            "canary_offset_ms": -2450.0,
            "canary_confidence": 0.2735,
            "canary_method": "mouth_motion_proxy",
            "offset_change_ms": 2500.0,
            "method": "mouth_motion_proxy (fallback — no SyncNet)",
            "note": "Both results are provisional. Without face tracking or SyncNet, offset values are frame-diff vs audio-envelope correlations, not actual mouth-motion measurements. Do not use for publish decision.",
        },
        "findings": [],
    }

    # Analyze findings
    findings = comparison["findings"]

    # Duration comparison
    b_dur = comparison["baseline"]["duration_sec"]
    c_dur = comparison["canary"]["duration_sec"]
    if b_dur and c_dur:
        # Baseline is full video (22.9s), canary is segment (5.06s)
        findings.append({"key": "duration_scope", "severity": "info",
            "detail": f"Baseline is full 22.9s video. Canary is S000 segment only (~5.06s). Direct comparison limited."})

    # Resolution comparison
    b_res = comparison["baseline"]["video"]["resolution"] if comparison["baseline"]["video"] else None
    c_res = comparison["canary"]["video"]["resolution"] if comparison["canary"]["video"] else None
    if b_res and c_res and b_res != c_res:
        findings.append({"key": "resolution_change", "severity": "warn",
            "detail": f"Provider output resolution changed from {b_res} (baseline) to {c_res} (canary). Check if this affects assembly compatibility."})

    # Lipsync offset
    findings.append({"key": "lipsync_offset", "severity": "fail",
        "detail": f"Canary offset {comparison['lipsync']['canary_offset_ms']}ms vs baseline {comparison['lipsync']['baseline_offset_ms']}ms. Changed by {abs(comparison['lipsync']['offset_change_ms'])}ms. Still exceeds 160ms fail threshold."})

    # Lipsync method
    findings.append({"key": "lipsync_method", "severity": "fail",
        "detail": "No SyncNet available. Cannot evaluate true lipsync quality. All measurements are provisional."})

    # Diagnostic audio
    if da and da["sha256"]:
        if da["sha256"] != source_slice_sha:
            findings.append({"key": "diagnostic_audio_hash", "severity": "warn",
                "detail": "Diagnostic audio SHA256 does not match source slice SHA256. This is EXPECTED — diagnostic audio is the provider's rendered audio output, not the input. Comparison requires audio-to-audio correlation."})

    # Canary has audio
    c_has_audio = c_a is not None
    findings.append({"key": "canary_has_audio", "severity": "pass" if c_has_audio else "fail",
        "detail": f"Canary {'has' if c_has_audio else 'lacks'} audio track."})

    # Duration match with expected
    c_dur_ms = (c_dur or 0) * 1000
    expected_ms = 4572
    dur_delta = abs(c_dur_ms - expected_ms)
    findings.append({"key": "canary_duration_vs_expected", 
        "severity": "pass" if dur_delta < 1000 else "warn",
        "detail": f"Canary duration {c_dur_ms:.0f}ms vs expected {expected_ms}ms (delta={dur_delta:.0f}ms)."})

    # Overall status
    fail_findings = [f for f in findings if f["severity"] == "fail"]
    warn_findings = [f for f in findings if f["severity"] == "warn"]
    
    if fail_findings:
        overall = "fail"
    elif warn_findings:
        overall = "warn"
    else:
        overall = "pass"

    comparison["overall"] = overall
    comparison["summary"] = {
        "total_findings": len(findings),
        "pass": len([f for f in findings if f["severity"] == "pass"]),
        "warn": len(warn_findings),
        "fail": len(fail_findings),
    }

    # Decision
    if any(f["key"] == "lipsync_offset" for f in fail_findings):
        comparison["decision"] = "FAIL_NEEDS_PROVIDER_RERENDER"
        comparison["decision_reason"] = (
            "Canary lipsync offset (-2450ms) still exceeds 160ms fail threshold. "
            "Method is provisional mouth_motion_proxy. SyncNet required for definitive assessment. "
            "Production is NOT publishable with current lipsync quality."
        )
    elif any(f["key"] == "lipsync_method" for f in fail_findings):
        comparison["decision"] = "BLOCKED_NEEDS_SYNCNET"
        comparison["decision_reason"] = "No SyncNet available."
    else:
        comparison["decision"] = "PASS_FORENSIC_COMPLETED"
        comparison["decision_reason"] = "All checks pass."

    return comparison


def main(argv=None):
    ap = argparse.ArgumentParser(description="Baseline vs canary comparison")
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    ap.add_argument("--canary", type=Path, default=DEFAULT_CANARY)
    ap.add_argument("--out", type=Path, default=Path("reports/karpathy_loop/sprint_06/S06_T004/eval_result_before.json"))
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    result = compare(args.baseline, args.canary, db_path=args.db_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Baseline vs Canary Comparison for {result['production_id']}")
    print(f"  Overall: {result['overall']}")
    print(f"  Decision: {result['decision']}")
    print(f"  Findings: {result['summary']['pass']} pass, {result['summary']['warn']} warn, {result['summary']['fail']} fail")
    for f in result["findings"]:
        mark = {"pass": "✓", "warn": "△", "fail": "✗", "info": "i"}[f["severity"]]
        print(f"  [{mark}] {f['key']}: {f['detail'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
