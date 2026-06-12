#!/usr/bin/env python3
"""gates.py — Per-project gate ledger for the YTchannel production pipeline.

The ledger is the enforcement primitive that makes ungated Higgsfield spend
impossible. Each gate records its status AND the SHA-256 of the artifact it
approved, so that editing an artifact after its gate was passed invalidates
that gate (and, by extension, every downstream gate that depends on it).

Ledger location: Videos/Projects/{project_id}/gates.json

Public API (imported by generate_media.py, tts.py, assemble.py, approve.py):
    record_gate(project_id, gate, status, artifact_path=None, extra=None, forced=False)
    require_gates(project_id, gate_names, artifact_hashes=None, allow_forced=False)
    read_ledger(project_id)
    artifact_sha256(path)

CLI:
    python3 scripts/gates.py show <project_id>
    python3 scripts/gates.py record <project_id> <gate> <status> [--artifact PATH] [--force-unsafe]
    python3 scripts/gates.py require <project_id> <gate> [<gate> ...] [--artifact gate=PATH ...]

Gate names used by the pipeline (blueprint §2/§6):
    script_review        (G1)  — gates tts.py, storyboard.py
    storyboard_review    (G2)  — gates compile_media_prompts.py
    media_plan_review    (G3)  — gates generate_media.py
    budget               (G4)  — gates generate_media.py
    render_approval      (G7)  — gates generate_media.py (the human spend switch)
    media_qa             (G8)  — gates assemble.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "Videos" / "Projects"

VALID_STATUSES = {"pass", "fail", "blocked", "pending"}

# Canonical gate -> human-readable command to (re)run it. Used in error messages.
GATE_COMMANDS = {
    "script_review": "python3 scripts/review_script.py <script.json> --output-json <review.json> --record-gate",
    "storyboard_review": "python3 scripts/review_storyboard.py <storyboard.json> --record-gate",
    "media_plan_review": "python3 scripts/review_media_plan.py <media_plan.json> --record-gate",
    "budget": "python3 scripts/budget.py <media_plan.json> --record-gate",
    "render_approval": "python3 scripts/approve.py <project_id> --gate render",
    "media_qa": "python3 scripts/qa_media.py <media_plan.json> --record-gate",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def ledger_path(project_id: str) -> Path:
    return project_dir(project_id) / "gates.json"


def artifact_sha256(path) -> str | None:
    """Return the SHA-256 hex digest of a file, or None if the path is missing."""
    if path is None:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_ledger(project_id: str) -> dict:
    """Load the gate ledger for a project. Returns an empty skeleton if absent."""
    lp = ledger_path(project_id)
    if not lp.exists():
        return {"project_id": project_id, "gates": {}}
    try:
        data = json.loads(lp.read_text())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Corrupt gate ledger {lp}: {e}")
    data.setdefault("project_id", project_id)
    data.setdefault("gates", {})
    return data


def _write_ledger(project_id: str, data: dict) -> Path:
    lp = ledger_path(project_id)
    lp.parent.mkdir(parents=True, exist_ok=True)
    tmp = lp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, lp)  # atomic
    return lp


def record_gate(project_id: str, gate: str, status: str, artifact_path=None,
                extra: dict | None = None, forced: bool = False,
                approved_by: str | None = None) -> dict:
    """Record (or overwrite) a gate entry in the project ledger.

    Records the SHA-256 of artifact_path so that later edits invalidate the gate.
    Returns the entry written.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid gate status {status!r}; must be one of {sorted(VALID_STATUSES)}")

    data = read_ledger(project_id)
    entry = {
        "gate": gate,
        "status": status,
        "recorded_at": _now(),
        "artifact_path": str(artifact_path) if artifact_path else None,
        "artifact_sha256": artifact_sha256(artifact_path),
        "forced": bool(forced),
    }
    if approved_by:
        entry["approved_by"] = approved_by
    if extra:
        entry["extra"] = extra
    data["gates"][gate] = entry
    _write_ledger(project_id, data)
    return entry


def gate_status(project_id: str, gate: str) -> dict | None:
    return read_ledger(project_id)["gates"].get(gate)


def _stale(entry: dict, current_hashes: dict | None) -> str | None:
    """Return a staleness reason if the recorded artifact hash no longer matches.

    current_hashes maps gate_name -> expected sha256 of the live artifact. If a
    gate isn't in current_hashes we re-hash the recorded artifact_path itself.
    Returns None if fresh.
    """
    gate = entry["gate"]
    recorded = entry.get("artifact_sha256")
    if recorded is None:
        # Gate did not bind to an artifact (e.g. human render_approval w/o file) — never stale.
        return None
    if current_hashes and gate in current_hashes:
        live = current_hashes[gate]
    else:
        live = artifact_sha256(entry.get("artifact_path"))
    if live is None:
        return f"artifact missing for gate {gate!r} (was {entry.get('artifact_path')})"
    if live != recorded:
        return f"artifact for gate {gate!r} changed since approval (edit invalidates the gate)"
    return None


def require_gates(project_id: str, gate_names, artifact_hashes: dict | None = None,
                  allow_forced: bool = True) -> None:
    """Hard guard. Exit 1 (with a human-readable message) unless ALL named gates
    are status=pass AND their recorded artifact hashes still match.

    Spending tools call this before any external/billable operation. Set
    allow_forced=False to reject even gates that were forced via --force-unsafe.
    """
    data = read_ledger(project_id)
    gates = data["gates"]
    problems = []

    for gate in gate_names:
        entry = gates.get(gate)
        if entry is None:
            problems.append(
                f"  ✗ gate {gate!r} has never been recorded.\n"
                f"    run: {GATE_COMMANDS.get(gate, '(record this gate)')}")
            continue
        if entry.get("status") != "pass":
            problems.append(
                f"  ✗ gate {gate!r} status is {entry.get('status')!r}, not 'pass'.\n"
                f"    run: {GATE_COMMANDS.get(gate, '(re-run this gate)')}")
            continue
        if entry.get("forced") and not allow_forced:
            problems.append(f"  ✗ gate {gate!r} was force-passed (--force-unsafe) and forced gates are not allowed here.")
            continue
        reason = _stale(entry, artifact_hashes)
        if reason:
            problems.append(
                f"  ✗ {reason}\n"
                f"    re-run: {GATE_COMMANDS.get(gate, '(re-approve this gate)')}")

    if problems:
        sys.stderr.write(
            f"BLOCKED: required gates not satisfied for project {project_id!r}:\n"
            + "\n".join(problems)
            + "\n  (override only in emergencies with --force-unsafe — it is logged in gates.json)\n")
        sys.exit(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Per-project gate ledger.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Print the gate ledger for a project")
    p_show.add_argument("project_id")

    p_rec = sub.add_parser("record", help="Record a gate result")
    p_rec.add_argument("project_id")
    p_rec.add_argument("gate")
    p_rec.add_argument("status", choices=sorted(VALID_STATUSES))
    p_rec.add_argument("--artifact", default=None)
    p_rec.add_argument("--approved-by", default=None)
    p_rec.add_argument("--force-unsafe", action="store_true",
                       help="Mark this gate as forced (logged as forced:true)")

    p_req = sub.add_parser("require", help="Exit 1 unless all named gates pass + are fresh")
    p_req.add_argument("project_id")
    p_req.add_argument("gates", nargs="+")

    args = ap.parse_args(argv)

    if args.cmd == "show":
        data = read_ledger(args.project_id)
        if not data["gates"]:
            print(f"(no gates recorded for {args.project_id})")
            return 0
        print(f"=== gate ledger: {args.project_id} ===")
        for name, e in data["gates"].items():
            forced = "  [FORCED]" if e.get("forced") else ""
            print(f"  {name:20s} {e['status']:8s} {e.get('recorded_at','')}{forced}")
            if e.get("artifact_path"):
                print(f"      artifact: {e['artifact_path']}  sha={str(e.get('artifact_sha256'))[:12]}")
        return 0

    if args.cmd == "record":
        if args.force_unsafe and args.status == "pass":
            sys.stderr.write(
                f"\033[31m⚠ FORCE-UNSAFE: recording gate {args.gate!r}=pass for "
                f"{args.project_id!r} WITHOUT verification. This is logged.\033[0m\n")
        entry = record_gate(args.project_id, args.gate, args.status,
                            artifact_path=args.artifact, forced=args.force_unsafe,
                            approved_by=args.approved_by)
        print(f"recorded {args.gate}={args.status}"
              f"{' (FORCED)' if entry['forced'] else ''} for {args.project_id}")
        return 0

    if args.cmd == "require":
        require_gates(args.project_id, args.gates)
        print(f"OK: all gates satisfied for {args.project_id}: {', '.join(args.gates)}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
