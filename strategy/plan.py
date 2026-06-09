#!/usr/bin/env python3
"""
plan.py — deterministic state manager for TIMEPLAN.yaml

Why this exists:
    The assistant (kiro-cli) and the user jointly work the plan across many sessions.
    Hand-editing YAML risks corruption. This CLI does safe reads/writes and computes
    "what's next" from the dependency graph, so state is always consistent.

Usage:
    python3 plan.py status                 # summary + current in_progress + what's unblocked
    python3 plan.py next                    # the single best next step to do
    python3 plan.py list [--phase P1]       # list steps (optionally by phase), with status
    python3 plan.py show <ID>               # full detail for one step
    python3 plan.py start <ID>              # mark in_progress (checks deps)
    python3 plan.py done <ID>               # mark done (checks deps satisfied)
    python3 plan.py block <ID> "reason"     # mark blocked with a reason
    python3 plan.py unblock <ID>            # back to todo
    python3 plan.py note <ID> "text"        # append a timestamped note
    python3 plan.py progress                # one-line progress bar

Requires: PyYAML (pip install pyyaml). Falls back to a tiny built-in parser-free
path only for reading is NOT supported; PyYAML is required for writes.
"""
import sys
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_PATH = os.path.join(HERE, "TIMEPLAN.yaml")

STATUSES = {"todo", "in_progress", "blocked", "done"}
ICON = {"todo": "[ ]", "in_progress": "[~]", "blocked": "[!]", "done": "[x]"}


def _require_yaml():
    try:
        import yaml  # noqa
        return yaml
    except ImportError:
        sys.exit("ERROR: PyYAML is required. Install with: pip install pyyaml")


def load():
    yaml = _require_yaml()
    with open(PLAN_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save(data):
    yaml = _require_yaml()
    tmp = PLAN_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
    os.replace(tmp, PLAN_PATH)  # atomic


def index(data):
    return {s["id"]: s for s in data["steps"]}


def find(data, sid):
    by_id = index(data)
    if sid not in by_id:
        sys.exit(f"ERROR: step id '{sid}' not found. Use 'list' to see ids.")
    return by_id[sid]


def deps_satisfied(step, by_id):
    return all(by_id.get(d, {}).get("status") == "done" for d in step.get("depends_on", []))


def unblocked_todos(data):
    by_id = index(data)
    out = []
    for s in data["steps"]:
        if s["status"] == "todo" and deps_satisfied(s, by_id):
            out.append(s)
    return out


def now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")


def cmd_status(data):
    by_id = index(data)
    counts = {k: 0 for k in STATUSES}
    for s in data["steps"]:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    total = len(data["steps"])
    done = counts["done"]
    print(f"=== {data['meta']['business']} ===")
    print(f"Niche: {data['meta']['niche']}")
    print(f"Progress: {done}/{total} done | {counts['in_progress']} in progress | "
          f"{counts['blocked']} blocked | {counts['todo']} todo")
    print()
    inprog = [s for s in data["steps"] if s["status"] == "in_progress"]
    if inprog:
        print("IN PROGRESS:")
        for s in inprog:
            print(f"  {ICON[s['status']]} {s['id']}  {s['title']}")
        print()
    blocked = [s for s in data["steps"] if s["status"] == "blocked"]
    if blocked:
        print("BLOCKED:")
        for s in blocked:
            note = (s.get("notes") or "").strip().splitlines()
            reason = note[-1] if note else ""
            print(f"  {ICON[s['status']]} {s['id']}  {s['title']}  {('- ' + reason) if reason else ''}")
        print()
    nxt = unblocked_todos(data)
    print("READY TO START (dependencies satisfied):")
    if not nxt:
        print("  (none — everything is in progress, blocked, or done)")
    for s in nxt[:6]:
        print(f"  {ICON[s['status']]} {s['id']}  {s['title']}  (~{s.get('est_hours','?')}h)")
    print()
    print("Tip: 'python3 plan.py next' for the single recommended step; 'show <ID>' for detail.")


def cmd_next(data):
    nxt = unblocked_todos(data)
    if not nxt:
        print("No unblocked todo steps. Run 'status' to see in-progress/blocked items.")
        return
    s = nxt[0]
    print(f"NEXT: {s['id']} — {s['title']}  (phase {s['phase']}, ~{s.get('est_hours','?')}h)")
    print(f"  Deliverable: {s['deliverable']}")
    print(f"  How:         {s['how']}")
    print(f"  Acceptance:  {s['acceptance']}")
    print()
    print(f"  Start it with: python3 plan.py start {s['id']}")


def cmd_list(data, phase=None):
    for ph in data["phases"]:
        if phase and ph["id"] != phase:
            continue
        steps = [s for s in data["steps"] if s["phase"] == ph["id"]]
        if not steps:
            continue
        print(f"\n{ph['name']}")
        for s in steps:
            print(f"  {ICON[s['status']]} {s['id']}  {s['title']}")


def cmd_show(data, sid):
    s = find(data, sid)
    by_id = index(data)
    print(f"{s['id']} — {s['title']}")
    print(f"  Phase:       {s['phase']}")
    print(f"  Status:      {s['status']}")
    print(f"  Depends on:  {s.get('depends_on') or '(none)'}  "
          f"[{'satisfied' if deps_satisfied(s, by_id) else 'NOT satisfied'}]")
    print(f"  Deliverable: {s['deliverable']}")
    print(f"  Est hours:   {s.get('est_hours','?')}")
    print(f"  How:         {s['how']}")
    print(f"  Acceptance:  {s['acceptance']}")
    print(f"  Notes:\n{s.get('notes') or '    (none)'}")


def cmd_start(data, sid):
    by_id = index(data)
    s = find(data, sid)
    if not deps_satisfied(s, by_id):
        unmet = [d for d in s.get("depends_on", []) if by_id.get(d, {}).get("status") != "done"]
        sys.exit(f"ERROR: cannot start {sid}; unmet dependencies: {unmet}")
    s["status"] = "in_progress"
    save(data)
    print(f"OK: {sid} -> in_progress")


def cmd_done(data, sid):
    by_id = index(data)
    s = find(data, sid)
    if not deps_satisfied(s, by_id):
        unmet = [d for d in s.get("depends_on", []) if by_id.get(d, {}).get("status") != "done"]
        sys.exit(f"ERROR: cannot complete {sid}; unmet dependencies: {unmet}")
    s["status"] = "done"
    _append_note(s, "completed")
    save(data)
    print(f"OK: {sid} -> done")
    newly = [x["id"] for x in unblocked_todos(data) if sid in x.get("depends_on", [])]
    if newly:
        print(f"Unlocked: {', '.join(newly)}")


def cmd_block(data, sid, reason):
    s = find(data, sid)
    s["status"] = "blocked"
    _append_note(s, f"BLOCKED: {reason}")
    save(data)
    print(f"OK: {sid} -> blocked ({reason})")


def cmd_unblock(data, sid):
    s = find(data, sid)
    s["status"] = "todo"
    _append_note(s, "unblocked")
    save(data)
    print(f"OK: {sid} -> todo")


def _append_note(step, text):
    stamp = f"[{now()}] {text}"
    existing = step.get("notes") or ""
    step["notes"] = (existing + ("\n" if existing.strip() else "") + stamp).strip()


def cmd_note(data, sid, text):
    s = find(data, sid)
    _append_note(s, text)
    save(data)
    print(f"OK: note added to {sid}")


def cmd_progress(data):
    total = len(data["steps"])
    done = sum(1 for s in data["steps"] if s["status"] == "done")
    width = 30
    filled = int(width * done / total) if total else 0
    bar = "#" * filled + "-" * (width - filled)
    pct = (100 * done // total) if total else 0
    print(f"[{bar}] {done}/{total} ({pct}%)")


def main():
    argv = sys.argv[1:]
    if not argv:
        argv = ["status"]
    cmd = argv[0]
    data = load()

    if cmd == "status":
        cmd_status(data)
    elif cmd == "next":
        cmd_next(data)
    elif cmd == "list":
        phase = None
        if "--phase" in argv:
            phase = argv[argv.index("--phase") + 1]
        cmd_list(data, phase)
    elif cmd == "show":
        cmd_show(data, argv[1])
    elif cmd == "start":
        cmd_start(data, argv[1])
    elif cmd == "done":
        cmd_done(data, argv[1])
    elif cmd == "block":
        cmd_block(data, argv[1], argv[2] if len(argv) > 2 else "")
    elif cmd == "unblock":
        cmd_unblock(data, argv[1])
    elif cmd == "note":
        cmd_note(data, argv[1], argv[2] if len(argv) > 2 else "")
    elif cmd == "progress":
        cmd_progress(data)
    else:
        sys.exit(f"Unknown command '{cmd}'. See header of plan.py for usage.")


if __name__ == "__main__":
    main()
