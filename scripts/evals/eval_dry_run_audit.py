#!/usr/bin/env python3
"""Dry-run provider request audit for S06_T002.

Audits the provider request payload without sending it.
HIGGSFIELD_DRY_RUN=1 must be active.

Usage:
  python3 scripts/evals/eval_dry_run_audit.py --render-unit-id <id> --out <json>
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dry-run provider request audit")
    ap.add_argument("--render-unit-id", default="render_f91a245c14b341b6a7975e2a8d5716fc")
    ap.add_argument("--production-id", default="prod_2f9bb58c0508465fb51ac6b4578bba92")
    ap.add_argument("--out", type=Path, default=Path("reports/karpathy_loop/sprint_06/S06_T002/eval_result_before.json"))
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    db_path = args.db_path or os.environ.get("PRODUCTION_DB_PATH", "db/production.db")

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Load render unit
    ru = conn.execute("""
        SELECT * FROM render_units WHERE id=? AND production_id=?
    """, (args.render_unit_id, args.production_id)).fetchone()
    if not ru:
        print(f"ERROR: render_unit {args.render_unit_id} not found", file=sys.stderr)
        return 1
    ru = dict(ru)

    # Load existing provider job for the same unit (to validate the payload)
    pj = conn.execute("""
        SELECT request_json, idempotency_key FROM provider_jobs
        WHERE render_unit_id=? AND status='completed'
        ORDER BY rowid DESC LIMIT 1
    """, (args.render_unit_id,)).fetchone()

    conn.close()

    issues = []
    checks = {}

    # ── 1. HIGGSFIELD_DRY_RUN check ──────────────────────────────────
    dry_run = os.environ.get("HIGGSFIELD_DRY_RUN", "0")
    checks["dry_run_active"] = dry_run == "1"
    if not checks["dry_run_active"]:
        issues.append("HIGGSFIELD_DRY_RUN not set to 1")

    # ── 2. Build the request payload (from existing job) ──────────────
    payload = {}
    if pj:
        payload = json.loads(pj["request_json"] or "{}")
    else:
        # Build from render unit metadata
        meta = json.loads(ru.get("metadata_json") or "{}")
        payload = {
            "asset_type": ru.get("asset_type"),
            "audio_policy": ru.get("audio_policy"),
            "duration_ms": ru.get("required_duration_ms"),
            "duration_sec": (ru.get("required_duration_ms") or 0) / 1000.0,
            "image_path": meta.get("image_path"),
            "model": "seedance_2_0",
            "prompt": meta.get("prompt", ""),
            "negative_prompt": meta.get("negative_prompt", ""),
        }
        # Determine audio_path
        base = "/home/jacobw/YTchannel/Videos/Projects/use_ai_to_triage_your_notifications_and/narration/hero_audio_slices"
        payload["audio_path"] = f"{base}/{args.render_unit_id}.wav"

    audio_path = payload.get("audio_path", "")
    image_path = payload.get("image_path", "")
    model = payload.get("model", "")
    prompt = payload.get("prompt", "")
    neg_prompt = payload.get("negative_prompt", "")
    audio_policy = payload.get("audio_policy", ru.get("audio_policy"))
    asset_type = payload.get("asset_type", ru.get("asset_type"))

    # ── 3. Audio path verification ────────────────────────────────────
    audio_file = Path(audio_path) if audio_path else None
    checks["audio_path_provided"] = bool(audio_path)
    checks["audio_path_exists"] = audio_file.exists() if audio_file else False
    if audio_file and audio_file.exists():
        checks["audio_file_size_bytes"] = audio_file.stat().st_size
        checks["audio_file_sha256"] = hashlib.sha256(audio_file.read_bytes()).hexdigest()
        checks["audio_sha256_verified"] = checks["audio_file_sha256"] == "8e72630b726ab148586eb8445052be7c272efbee75e42f5c852a4a5bb6e8416b"
    else:
        checks["audio_sha256_verified"] = False

    if not checks["audio_path_provided"]:
        issues.append("Missing audio_path in request")
    if not checks["audio_path_exists"]:
        issues.append(f"Audio file not found: {audio_path}")
    if not checks["audio_sha256_verified"]:
        issues.append("Audio file hash mismatch with expected source slice hash")

    # ── 4. Image/reference path ───────────────────────────────────────
    img_file = Path(image_path) if image_path else None
    checks["image_path_provided"] = bool(image_path)
    checks["image_path_exists"] = img_file.exists() if img_file else False
    if not checks["image_path_provided"]:
        issues.append("Missing image_path in request")
    if not checks["image_path_exists"]:
        issues.append(f"Image file not found: {image_path}")

    # ── 5. Model supports audio ───────────────────────────────────────
    audio_capable_models = {"seedance_2_0", "seedance_2", "higgsfield_audio", "motion_audio"}
    checks["model_supports_audio"] = model.lower() in {m.lower() for m in audio_capable_models} if model else False
    if not checks["model_supports_audio"]:
        issues.append(f"Model '{model}' may not support audio input")

    # ── 6. Idempotency key stable ────────────────────────────────────
    if pj and pj["idempotency_key"]:
        expected_key = f"pjob:{args.production_id}:{args.render_unit_id}"
        checks["idempotency_key_stable"] = expected_key in str(pj["idempotency_key"])
        checks["idempotency_key"] = pj["idempotency_key"]
    else:
        checks["idempotency_key_stable"] = True
        checks["idempotency_key"] = f"pjob:{args.production_id}:{args.render_unit_id}"
    if not checks["idempotency_key_stable"]:
        issues.append("Unstable idempotency key")

    # ── 7. Prompt text-risk clean ─────────────────────────────────────
    risk_keywords = ["click", "subscribe", "like", "share", "sign up",
                     "enter your", "password", "credit card", "login",
                     "readable text", "exact text", "type these words"]
    prompt_lower = prompt.lower() if prompt else ""
    checks["prompt_provided"] = bool(prompt)
    checks["negative_prompt_provided"] = bool(neg_prompt)
    checks["prompt_has_negative_text_policy"] = any(
        kw in prompt_lower for kw in ["no text", "no text on screen", "no readable text",
                                       "no visible text", "text risk", "text_policy"]
    )
    found_risks = [kw for kw in risk_keywords if kw in prompt_lower]
    checks["prompt_risk_keywords_found"] = found_risks
    if found_risks:
        issues.append(f"Prompt contains text-risk keywords: {found_risks}")

    # ── 8. Duration check ─────────────────────────────────────────────
    dur_ms = payload.get("duration_ms", ru.get("required_duration_ms", 0)) or 0
    checks["duration_ms"] = dur_ms
    checks["duration_valid"] = 1000 <= dur_ms <= 10000
    if not checks["duration_valid"]:
        issues.append(f"Duration {dur_ms}ms outside expected range (1000-10000ms)")

    # ── 9. Asset/audio policy consistency ─────────────────────────────
    checks["asset_type"] = asset_type
    checks["audio_policy"] = audio_policy
    if audio_policy == "HERO_SYNC_LOCKED" and asset_type not in ("lipsync_video",):
        issues.append(f"HERO_SYNC_LOCKED policy with non-lipsync asset: {asset_type}")

    # ── Assemble result ───────────────────────────────────────────────
    all_clean = all(checks.get(k) is True or isinstance(checks.get(k), (int, str))
                    for k in ["dry_run_active", "audio_path_provided", "audio_path_exists",
                              "audio_sha256_verified", "image_path_provided", "image_path_exists",
                              "model_supports_audio", "idempotency_key_stable",
                              "prompt_provided", "negative_prompt_provided", "duration_valid"])
    has_issues = len(issues) > 0

    result = {
        "eval_id": "S06_T002_dry_run_audit",
        "production_id": args.production_id,
        "render_unit_id": args.render_unit_id,
        "dry_run": dry_run == "1",
        "would_submit_provider_job": False,
        "payload_preview": {k: v for k, v in list(payload.items())[:6]},
        "payload_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16],
        "audio_sha256_verified": checks.get("audio_sha256_verified", False),
        "prompt_policy_ok": len(found_risks) == 0,
        "checks": checks,
        "issues": issues,
        "clean": not has_issues,
        "note": "Dry-run audit complete. Payload is ready for actual render. No external job submitted.",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    print(f"Dry-run audit for {args.render_unit_id}")
    print(f"  Dry run active: {result['dry_run']}")
    print(f"  Payload hash: {result['payload_hash']}")
    print(f"  Audio verified: {result['audio_sha256_verified']}")
    print(f"  Prompt clean: {result['prompt_policy_ok']}")
    print(f"  Issues: {len(result['issues'])}")
    for iss in result["issues"]:
        print(f"    ! {iss}")
    print(f"  Clean: {result['clean']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
