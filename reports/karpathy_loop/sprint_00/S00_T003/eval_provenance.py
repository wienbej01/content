#!/usr/bin/env python3
"""DB provenance eval for S00_T003.

Checks the provenance chain for hero sync-locked render units.
Deterministic, read-only, no provider calls.
"""
import json
import sqlite3
import os
import pathlib

PROD = "prod_2f9bb58c0508465fb51ac6b4578bba92"
DB = os.environ.get("PRODUCTION_DB_PATH", "db/production.db")
EXPORT_DIR = pathlib.Path("reports/karpathy_loop/sprint_00/S00_T003/db_exports")
OUTPUT = pathlib.Path("reports/karpathy_loop/sprint_00/S00_T003/eval_result_before.json")

checks = []
issues = []

def add_check(name, passed, detail, threshold=""):
    checks.append({"check": name, "pass": bool(passed), "detail": str(detail), "threshold": threshold})
    return bool(passed)

conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row

# 1. EXPORT_COMPLETE
expected_tables = [
    "productions", "stage_runs", "timeline_spans", "render_units",
    "provider_jobs", "artifacts", "validations", "deliverables",
    "change_requests", "production_events", "creative_beats"
]
export_files = [f.name for f in EXPORT_DIR.iterdir() if f.suffix == ".jsonl"]
missing = [t for t in expected_tables if f"{t}.jsonl" not in export_files]
export_ok = add_check("EXPORT_COMPLETE", len(missing) == 0,
                      f"{len(export_files)} JSONL files; missing={missing}",
                      "all 11 tables exported")
if not export_ok:
    issues.append({"class": "F-QA-002", "severity": "major",
        "description": f"Missing table exports: {missing}",
        "detail": "DB export incomplete"})

# 2. VALID_UNITS_PROVENANCE
valid_units = conn.execute(
    "SELECT id, label, asset_type, lipsync_required, status, active_artifact_id "
    "FROM render_units WHERE production_id=? AND status='valid'",
    (PROD,)).fetchall()

units_without_artifact = [r for r in valid_units if not r["active_artifact_id"]]
prov_ok = add_check("VALID_UNITS_PROVENANCE", len(units_without_artifact) == 0,
                    f"{len(valid_units)} valid units; {len(units_without_artifact)} without artifact",
                    "all valid units have active_artifact_id")
if not prov_ok:
    for r in units_without_artifact:
        issues.append({"class": "F-PROV-001", "severity": "major",
            "description": f"Unit {r['label']} ({r['id'][:20]}...) valid but has no active_artifact_id",
            "detail": f"lipsync={r['lipsync_required']} type={r['asset_type']}"})

# 3. HERO_AUDIO_PROVENANCE
hero_units = conn.execute(
    "SELECT id, label, required_start_ms, required_end_ms, audio_policy, "
    "final_audio_source, master_audio_artifact_id, master_audio_sha256 "
    "FROM render_units WHERE production_id=? AND status='valid' AND lipsync_required=1",
    (PROD,)).fetchall()

hero_no_master = [r for r in hero_units if not r["master_audio_artifact_id"]]
hero_ok = add_check("HERO_AUDIO_PROVENANCE", len(hero_no_master) == 0,
                    f"{len(hero_units)} HERO units; {len(hero_no_master)} without master_audio",
                    "all HERO units have master_audio_artifact_id")
if hero_no_master:
    for r in hero_no_master:
        issues.append({"class": "F-PROV-001", "severity": "major",
            "description": f"Hero unit {r['label']} has no master_audio_artifact_id",
            "detail": f"source={r['final_audio_source']}"})

# Check if both hero units share the SAME master audio (provenance gap)
if len(hero_units) >= 2:
    master_hashes = set(r["master_audio_sha256"] for r in hero_units if r["master_audio_sha256"])
    shared = len(master_hashes) < len(hero_units)
    if shared:
        issues.append({"class": "F-PROV-001", "severity": "major",
            "description": f"Both hero units share the same master audio hash ({', '.join(master_hashes)[:16]}...) — no per-slice provenance",
            "detail": "Cannot prove which audio slice was sent to provider for each hero unit"})

# Shared master check
if len(hero_units) >= 2:
    master_artifacts = set(r["master_audio_artifact_id"] for r in hero_units if r["master_audio_artifact_id"])
    shared_master = len(master_artifacts) == 1 and len(hero_units) > 1
    add_check("SHARED_MASTER_AUDIO", not shared_master,
              f"{len(hero_units)} HERO units share {len(master_artifacts)} master audio artifacts",
              "each HERO unit should have its own audio slice reference")

# 4. PROVIDER_JOB_STATUS
valid_unit_ids = tuple(r["id"] for r in valid_units)
if len(valid_unit_ids) == 1:
    valid_unit_ids_str = f"('{valid_unit_ids[0]}')"
else:
    valid_unit_ids_str = str(valid_unit_ids)

hero_jobs = conn.execute(f"""
    SELECT pj.id, pj.render_unit_id, pj.status, pj.external_job_id,
           ru.label, ru.lipsync_required
    FROM provider_jobs pj
    JOIN render_units ru ON ru.id = pj.render_unit_id
    WHERE pj.production_id=? AND pj.render_unit_id IN {valid_unit_ids_str}
    ORDER BY ru.label
""", (PROD,)).fetchall()

non_completed = [r for r in hero_jobs if r["status"] != "completed"]
jobs_ok = add_check("PROVIDER_JOB_STATUS", len(non_completed) == 0,
                    f"{len(hero_jobs)} provider jobs for valid units; {len(non_completed)} not completed",
                    "all provider jobs for valid units have status=completed")
if non_completed:
    for r in non_completed:
        issues.append({"class": "F-PROV-001", "severity": "major",
            "description": f"Provider job for {r['label']} has status={r['status']}, not 'completed'",
            "detail": f"job_id={r['id'][:20]}... ext_id={r['external_job_id'][:16] if r['external_job_id'] else 'N/A'}..."})

# 5. DELIVERABLE_PATH_COLLISION
deliverables = conn.execute(
    "SELECT d.id, d.variant, d.status, a.uri, a.sha256, a.size_bytes, d.qa_validation_id "
    "FROM deliverables d JOIN artifacts a ON d.artifact_id = a.id "
    "WHERE d.production_id=? AND d.status IN ('published','assembled')",
    (PROD,)).fetchall()

uris = {}
collisions = []
for r in deliverables:
    uri = r["uri"]
    if uri in uris:
        coll_dup = r["id"]
        coll_first = uris[uri]
        collisions.append({"uri": uri, "first": coll_first, "duplicate": coll_dup})
    uris[uri] = r["id"]

coll_ok = add_check("DELIVERABLE_PATH_COLLISION", len(collisions) == 0,
                    f"{len(deliverables)} deliverables; {len(collisions)} path collisions",
                    "0 path collisions")
if collisions:
    for c in collisions:
        issues.append({"class": "F-PROV-001", "severity": "major",
            "description": f"Path collision: {c['uri']} — {c['first']} and {c['duplicate']} share same path",
            "detail": "Deliverables overwrite each other on disk"})

# 6. QA_LIPSYNC_GATE
qa_final = conn.execute(
    "SELECT * FROM validations WHERE production_id=? AND validator_name='qa_final'",
    (PROD,)).fetchall()
has_lipsync_check = False
for r in qa_final:
    evidence = json.loads(r["evidence_json"] or "{}")
    contract_checks = evidence.get("contract_checks", {})
    # Check for any keys that suggest lipsync/timing validation
    lipsync_keywords = ["lipsync", "sync", "audio_offset", "timing", "av_sync",
                        "mouth", "phoneme", "wav2lip", "syncnet"]
    evidence_str = json.dumps(contract_checks).lower()
    for kw in lipsync_keywords:
        if kw in evidence_str:
            has_lipsync_check = True
            break

qa_ok = add_check("QA_LIPSYNC_GATE", has_lipsync_check,
                  f"{len(qa_final)} qa_final validations; lipsync check present: {has_lipsync_check}",
                  "qa_final should include lipsync/audio-sync check")
if not has_lipsync_check:
    issues.append({"class": "F-QA-001", "severity": "major",
        "description": "qa_final validation does not check lipsync/audio sync",
        "detail": "4 qa_final validations exist, none reference lipsync/audio_offset/SyncNet/Wav2Lip"})

conn.close()

# Summary
all_pass = all(c["pass"] for c in checks)
summary = {
    "eval_id": "S00_T003_provenance",
    "subject": "db/production.db",
    "production_id": PROD,
    "timestamp": "2026-06-23T23:22:00+08:00",
    "overall_pass": all_pass,
    "total_checks": len(checks),
    "checks_passed": sum(1 for c in checks if c["pass"]),
    "checks_failed": sum(1 for c in checks if not c["pass"]),
    "checks": checks,
    "issues": issues,
    "summary": {"pass": sum(1 for c in checks if c["pass"]),
                 "fail": sum(1 for c in checks if not c["pass"]),
                 "total": len(checks)}
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(summary, indent=2))

print(f"Provenance Eval: {summary['checks_passed']}/{summary['total_checks']} checks passed")
for c in checks:
    status = "PASS" if c["pass"] else "FAIL"
    print(f"  [{status}] {c['check']}: {c['detail']}")
print(f"\nIssues found: {len(issues)}")
for iss in issues:
    print(f"  {iss['class']} [{iss['severity']}]: {iss['description']}")
