#!/usr/bin/env python3
"""tools/sprint_runner.py — autonomous evidence-based sprint execution driver.

Drives a sprint from the planning artifacts: for each ticket, run
ENGINEER -> AUDIT -> VALIDATE with flowback (repair loops), routing each phase to the
model/effort appropriate to the ticket's execution class. Stops ONLY on critical user
input: a paid call, a gate approval, a BLOCKED, max repair cycles, or a wave-gate review.

Mechanism: spawns headless `claude -p` sessions, one per phase, invoking the role skills
(``/execute-ticket``, ``/audit-ticket``, ``/validate-scope``). Each session runs in
``YT_TEST_MODE=1`` so NO paid provider call is possible during automated phases; the real
paid run (gate_a_spend) is intentionally NOT automated.

Model routing (alias -> GLM tier via ANTHROPIC_DEFAULT_*_MODEL env):
  engineer   ROUTINE -> haiku/medium COMPLEX -> sonnet/high   REASONING_CRITICAL -> opus/max
  auditor    sonnet/high (REASONING_CRITICAL -> opus/max)
  validator  per-ticket sonnet/medium ; wave/final gate -> opus/max

Safety rails (enforced via --append-system-prompt + YT_TEST_MODE):
  - engineer may NOT self-accept; auditor does NOT repair; validator is independent.
  - any paid call / gate approval / irreversible action -> agent emits HUMAN_REQUIRED and
    stops; the runner then stops and asks the user.

Restartable: reads sprint STATE.json every run, so it resumes where it left off.

Usage:
  python3 tools/sprint_runner.py --dry-run                 # preview routing + plan
  python3 tools/sprint_runner.py --only S9-C03             # drive one ticket end-to-end
  python3 tools/sprint_runner.py                           # drive all remaining tickets
  python3 tools/sprint_runner.py --max-cycles 3 --per-call-timeout 1800
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SPRINT = REPO / "reports" / "recovery" / "S9"

# --------------------------------------------------------------------------- #
# Model routing config
# --------------------------------------------------------------------------- #
# alias -> (env var that remaps the alias, GLM model id). Override in your shell
# to use different tiers; the runner sets these for every child session.
MODEL_ENV = {
    "haiku":  ("ANTHROPIC_DEFAULT_HAIKU_MODEL",  "glm-4.7"),
    "sonnet": ("ANTHROPIC_DEFAULT_SONNET_MODEL", "glm-4.7"),
    "opus":   ("ANTHROPIC_DEFAULT_OPUS_MODEL",   "glm-5.2[1m]"),
}
EFFORT_FOR = {"haiku": "medium", "sonnet": "high", "opus": "max"}

ENGINEER_ALIAS = {
    "ROUTINE": "haiku",
    "COMPLEX": "sonnet",
    "REASONING_CRITICAL": "opus",
}


def engineer_alias(exec_class: str) -> str:
    return ENGINEER_ALIAS.get(exec_class, "sonnet")


def auditor_alias(exec_class: str) -> str:
    return "opus" if exec_class == "REASONING_CRITICAL" else "sonnet"


VALIDATOR_TICKET_ALIAS = "sonnet"
VALIDATOR_GATE_ALIAS = "opus"
VALIDATOR_TICKET_EFFORT = "medium"
VALIDATOR_GATE_EFFORT = "max"

MAX_CYCLES_DEFAULT = 3
PER_CALL_TIMEOUT_DEFAULT = 1800  # seconds per claude -p invocation

# --------------------------------------------------------------------------- #
# Runner <-> agent signal contract
# --------------------------------------------------------------------------- #
SIGNAL_RE = re.compile(r"RUNNER_SIGNAL:\s*([A-Z_]+)\s*(?:\|\s*(.*))?$", re.IGNORECASE)

# Auditor verdicts the runner treats as a pass (audit loop -> validate).
# PASS_WITH_FINDINGS is a pass where the auditor noted non-blocking (LOW) findings in the
# reason; any BLOCKING finding must be emitted as REPAIR_NEEDED, not soft-passed.
PASS_VERDICTS = {"PASS", "PASS_WITH_FINDINGS"}

# Out-of-vocabulary verdicts an agent may emit; normalize to the closest in-vocab verdict
# so the run flows back / proceeds instead of halting on an unexpected signal.
# FAIL = blocking issues found -> engineer repair (REPAIR_NEEDED), not a halt.
VERDICT_NORMALIZE = {
    "FAIL_WITH_FINDINGS": "REPAIR_NEEDED",
    "FAIL": "REPAIR_NEEDED",
}

# skill name -> role, to pick the prose-fallback token set below.
_ROLE_FROM_SKILL = {
    "execute-ticket": "engineer",
    "audit-ticket": "auditor",
    "validate-scope": "validator",
}

# When an agent states its verdict in prose but omits the RUNNER_SIGNAL line, recover it
# from the output's conclusion. Conservative: only distinctive tokens, scoped to the last
# few non-empty lines (where the verdict is stated), case-sensitive whole-word so "passed"
# never matches "PASS". Tokens normalize via VERDICT_NORMALIZE (FAIL -> REPAIR_NEEDED).
_PROSE_VERDICT_TOKENS = {
    "auditor": ["PASS_WITH_FINDINGS", "PASS", "REPAIR_NEEDED",
                "FAIL_WITH_FINDINGS", "FAIL", "BLOCKED"],
    "engineer": ["ENGINEER_DONE", "BLOCKED"],
}


def _scan_prose_verdict(out: str, role: str):
    """Fallback verdict recovery: scan the conclusion for a stated verdict token.

    Returns (canonical_verdict, reason) or None. The latest verdict-looking line wins;
    within a line, earlier (more-specific) tokens win.
    """
    tokens = _PROSE_VERDICT_TOKENS.get(role)
    if not tokens:
        return None
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    for line in reversed(lines[-12:]):
        for tok in tokens:
            # whole-word, case-sensitive: "PASS" must not match "passed" or sit inside
            # "PASS_WITH_FINDINGS" (handled by ordering + the A-Z_ lookarounds).
            if re.search(rf"(?<![A-Z_]){re.escape(tok)}(?![A-Z_])", line):
                return VERDICT_NORMALIZE.get(tok, tok), f"(recovered from prose) {line}"
    return None

SYSTEM_APPEND = """You are operating under an AUTOMATED sprint runner. In addition to your role skill:

HARD RULES:
- This run is in YT_TEST_MODE=1. Make NO paid provider calls (ElevenLabs/Higgsfield) and
  approve NO spend/gate (gate_a_spend / gate_b_review). If the work needs a paid call, a
  gate approval, or any irreversible/destructive action, emit the HUMAN_REQUIRED signal
  (below) and STOP — do not perform it.
- Role discipline: engineer implements exactly one ticket and may NOT self-accept; auditor
  reviews only and may NOT repair production code; validator is independent and runs the
  acceptance commands itself.
- Obey the no-hacks rule (root cause in pipeline code; never edit intermediate JSON/state/DB/outputs).

Your FINAL output line MUST be EXACTLY this and nothing may follow it:
RUNNER_SIGNAL: <VERDICT> | <one-line reason>
VERDICT vocabulary by role:
  engineer  : ENGINEER_DONE | BLOCKED | HUMAN_REQUIRED
  auditor   : PASS | PASS_WITH_FINDINGS | REPAIR_NEEDED | BLOCKED | HUMAN_REQUIRED
  validator : GO | NO_GO | BLOCKED | HUMAN_REQUIRED
PASS_WITH_FINDINGS = PASS for NON-BLOCKING (LOW) findings only (the runner proceeds to
validate, recording the findings). Any BLOCKING finding MUST be REPAIR_NEEDED, never
soft-passed. Anything outside this vocabulary halts the runner (unexpected-audit-signal).
"""

CHILD_ENV = {"YT_TEST_MODE": "1"}  # no paid calls during any automated phase

# Bin dirs the launching shell may not have had on PATH; prepend so subprocess can find
# `claude` and so claude's own child processes resolve tools.
EXTRA_PATH_DIRS = [
    str(Path.home() / ".local" / "bin"),
    "/usr/local/bin",
    str(Path.home() / ".npm-global" / "bin"),
    str(Path.home() / ".nvm" / "versions" / "node"),  # nvm node (best-effort)
]


def resolve_cli(cli: str) -> str:
    """Resolve the claude binary to an absolute path (shutil.which + common locations)."""
    found = shutil.which(cli)
    if found:
        return found
    for cand in (Path.home() / ".local" / "bin" / cli,
                 Path("/usr/local/bin") / cli,
                 Path.home() / ".npm-global" / "bin" / cli):
        if cand.exists() and os.access(cand, os.X_OK):
            return str(cand)
    return cli  # let the exec fail with a clear FileNotFoundError if truly absent


def ensure_path(env: dict) -> None:
    parts = env.get("PATH", "").split(os.pathsep)
    for d in EXTRA_PATH_DIRS:
        if d and d not in parts:
            parts.insert(0, d)
    env["PATH"] = os.pathsep.join(parts)


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #
def load_json(p: Path):
    return json.loads(p.read_text())


def save_json(p: Path, data) -> None:
    p.write_text(json.dumps(data, indent=2))


def parse_exec_class(ticket_path: Path) -> str:
    """Read the ticket's 'Execution class' metadata (ROUTINE/COMPLEX/REASONING_CRITICAL)."""
    m = re.search(r"Execution class:\s*\*{0,2}\s*(ROUTINE|COMPLEX|REASONING_CRITICAL)",
                  ticket_path.read_text(), re.IGNORECASE)
    return m.group(1).upper() if m else "COMPLEX"


def parse_dependencies(ticket_path: Path) -> list[str]:
    """Return ticket IDs listed in the 'Dependencies' metadata (empty if none)."""
    m = re.search(r"\*\*Dependencies:\*\*\s*(.+)", ticket_path.read_text())
    if not m:
        return []
    return re.findall(r"S9-C\d{2}", m.group(1))


def ticket_order(state: dict, sprint: Path) -> list[str]:
    """Wave order from STATE.json; each ticket in listed order."""
    ids = []
    for w in ("W1", "W2", "W3"):
        ids.extend(state.get("waves", {}).get(w, {}).get("tickets", []))
    # include any tickets present on disk but not in waves (safety)
    on_disk = sorted(p.stem for p in (sprint / "tickets").glob("S9-C*.md"))
    for tid in on_disk:
        if tid not in ids:
            ids.append(tid)
    return ids


def accepted_set(state: dict) -> set[str]:
    """Tickets that have passed validation and are accepted (GO)."""
    return set(state.get("completed_tickets") or [])


def completed_set(state: dict) -> set[str]:
    """Tickets that are fully implemented and may be awaiting validation or already accepted."""
    completed = set(state.get("completed_tickets") or [])
    implemented = set(state.get("implemented_awaiting_validation") or [])
    return completed | implemented


# --------------------------------------------------------------------------- #
# Core: run one headless claude phase
# --------------------------------------------------------------------------- #
def run_claude(skill: str, skill_args: str, alias: str, *, permission_mode: str,
               per_call_timeout: int, cli: str, effort: str | None = None) -> tuple[str, str, str]:
    """Invoke `claude -p "/<skill> <args>"` with the routed model/effort; parse the signal.

    Returns (verdict, reason, raw_stdout).
    """
    effort = effort or EFFORT_FOR[alias]
    env = os.environ.copy()
    for _alias, (envvar, model_id) in MODEL_ENV.items():
        # let an explicit export in the shell win, else use the configured GLM id
        env.setdefault(envvar, model_id)
    env.update(CHILD_ENV)
    ensure_path(env)

    argv = [
        cli, "-p",
        f"/{skill} {skill_args}".strip(),
        "--model", alias,
        "--effort", effort,
        "--permission-mode", permission_mode,
        "--append-system-prompt", SYSTEM_APPEND,
    ]
    print(f"\n=== [{skill} | model={alias} effort={effort}] args={skill_args!r} ===",
          flush=True)
    start = time.time()
    try:
        proc = subprocess.run(
            argv, cwd=str(REPO), env=env, capture_output=True, text=True,
            timeout=per_call_timeout,
        )
    except subprocess.TimeoutExpired:
        return ("HUMAN_REQUIRED", f"{skill} exceeded {per_call_timeout}s timeout", "")

    elapsed = int(time.time() - start)
    out = proc.stdout or ""
    verdict, reason = "HUMAN_REQUIRED", f"no RUNNER_SIGNAL parsed (rc={proc.returncode}, {elapsed}s)"
    for line in out.splitlines()[::-1]:
        m = SIGNAL_RE.match(line.strip())
        if m:
            verdict, reason = m.group(1).upper(), (m.group(2) or "").strip()
            break
    # Normalize out-of-vocabulary verdicts (FAIL -> REPAIR_NEEDED) so a blocking audit
    # flows back to the engineer instead of halting as an unexpected signal.
    verdict = VERDICT_NORMALIZE.get(verdict, verdict)
    # Fallback: if the agent stated its verdict in prose but omitted the RUNNER_SIGNAL
    # line, recover it from the conclusion rather than halting on "no RUNNER_SIGNAL".
    if verdict == "HUMAN_REQUIRED" and reason.startswith("no RUNNER_SIGNAL"):
        got = _scan_prose_verdict(out, _ROLE_FROM_SKILL.get(skill, ""))
        if got:
            verdict, reason = got
            print(f"[runner] no RUNNER_SIGNAL line; recovered verdict from prose: {verdict}",
                  flush=True)
    if verdict == "HUMAN_REQUIRED" and reason.startswith("no RUNNER_SIGNAL"):
        print(f"--- claude rc={proc.returncode} {elapsed}s ---\n{out[-2000:]}\n--- stderr ---\n{(proc.stderr or '')[-1000:]}", flush=True)
    else:
        print(f"--- {verdict} | {reason}  ({elapsed}s) ---", flush=True)
    return verdict, reason, out


# --------------------------------------------------------------------------- #
# Phase wrappers
# --------------------------------------------------------------------------- #
def engineer(tid: str, ticket_path: Path, exec_class: str, *, repair_note: str | None,
             **kw) -> tuple[str, str]:
    args = str(ticket_path)
    if repair_note:
        # Re-invoke execute-ticket with the audit/validation findings as a repair directive.
        args = f'{ticket_path} -- REPAIR: address the prior reviewer findings: {repair_note}'
    return run_claude("execute-ticket", args, engineer_alias(exec_class), **kw)[:2]


def auditor(tid: str, ticket_path: Path, exec_class: str, **kw) -> tuple[str, str]:
    return run_claude("audit-ticket", str(ticket_path), auditor_alias(exec_class), **kw)[:2]


def validator_ticket(tid: str, ticket_path: Path, **kw) -> tuple[str, str]:
    return run_claude(
        "validate-scope",
        str(ticket_path),
        VALIDATOR_TICKET_ALIAS,
        effort=VALIDATOR_TICKET_EFFORT,
        **kw,
    )[:2]


def validator_gate(label: str, sprint: Path, **kw) -> tuple[str, str]:
    # validate-scope accepts a Wave identifier or "sprint + final".
    return run_claude(
        "validate-scope",
        label,
        VALIDATOR_GATE_ALIAS,
        effort=VALIDATOR_GATE_EFFORT,
        **kw,
    )[:2]


# --------------------------------------------------------------------------- #
# Per-ticket flowback loop
# --------------------------------------------------------------------------- #
def process_ticket(tid: str, sprint: Path, *, max_cycles: int, skip_engineer: bool = False,
                   **kw) -> str:
    """Run engineer -> audit -> validate with flowback. Returns a STOP signal or 'ACCEPTED'."""
    ticket_path = sprint / "tickets" / f"{tid}.md"
    if not ticket_path.exists():
        return f"STOP:no-ticket:{tid}"
    exec_class = parse_exec_class(ticket_path)
    print(f"\n################## {tid} ({exec_class}) "
          f"{'(engineer already done -> audit)' if skip_engineer else ''} ##################",
          flush=True)

    # 1) ENGINEER (skip if STATE already shows it implemented/awaiting validation)
    if not skip_engineer:
        v, r = engineer(tid, ticket_path, exec_class, repair_note=None, **kw)
        if v in ("HUMAN_REQUIRED", "BLOCKED"):
            return f"STOP:{v}:{tid}: {r}"

    cycles = 0
    # 2) AUDIT (with repair flowback to engineer)
    while True:
        v, r = auditor(tid, ticket_path, exec_class, **kw)
        if v in ("HUMAN_REQUIRED", "BLOCKED"):
            return f"STOP:{v}:{tid}: {r}"
        if v in PASS_VERDICTS:
            if v == "PASS_WITH_FINDINGS":
                print(f"[audit] {tid}: PASS_WITH_FINDINGS — non-blocking findings recorded: {r}",
                      flush=True)
            break
        if v == "REPAIR_NEEDED":
            if cycles >= max_cycles:
                return f"STOP:max-audit-cycles:{tid}: {r}"
            cycles += 1
            print(f"[flowback] {tid}: engineer repair cycle {cycles}/{max_cycles} (audit: {r})", flush=True)
            ev, er = engineer(tid, ticket_path, exec_class, repair_note=r, **kw)
            if ev in ("HUMAN_REQUIRED", "BLOCKED"):
                return f"STOP:{ev}:{tid}: {er}"
            continue
        return f"STOP:unexpected-audit-signal:{tid}: {v} | {r}"

    # 3) VALIDATE (with flowback: NO_GO -> engineer repair -> re-audit -> re-validate)
    vcycles = 0
    while True:
        v, r = validator_ticket(tid, ticket_path, **kw)
        if v == "GO":
            print(f"[accepted] {tid}", flush=True)
            return "ACCEPTED"
        if v in ("HUMAN_REQUIRED", "BLOCKED"):
            return f"STOP:{v}:{tid}: {r}"
        if v == "NO_GO":
            if vcycles >= max_cycles:
                return f"STOP:max-validate-cycles:{tid}: {r}"
            vcycles += 1
            print(f"[flowback] {tid}: engineer repair cycle {vcycles}/{max_cycles} (validate: {r})", flush=True)
            ev, er = engineer(tid, ticket_path, exec_class, repair_note=r, **kw)
            if ev in ("HUMAN_REQUIRED", "BLOCKED"):
                return f"STOP:{ev}:{tid}: {er}"
            av, ar = auditor(tid, ticket_path, exec_class, **kw)  # re-audit the repair
            if av in ("HUMAN_REQUIRED", "BLOCKED"):
                return f"STOP:{av}:{tid}: {ar}"
            if av != "PASS":
                continue  # audit wants more repair; loop validate again
            continue
        return f"STOP:unexpected-validate-signal:{tid}: {v} | {r}"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Autonomous sprint execution driver.")
    ap.add_argument("--sprint", type=Path, default=DEFAULT_SPRINT, help="sprint dir (STATE.json + tickets/)")
    ap.add_argument("--only", action="append", default=[], help="only these ticket IDs (repeatable)")
    ap.add_argument("--max-cycles", type=int, default=MAX_CYCLES_DEFAULT, help="max repair cycles per phase")
    ap.add_argument("--per-call-timeout", type=int, default=PER_CALL_TIMEOUT_DEFAULT, help="seconds per claude -p call")
    ap.add_argument("--permission-mode", default="bypassPermissions",
                    help="claude --permission-mode (default bypassPermissions = autonomous)")
    ap.add_argument("--cli", default="claude", help="claude CLI binary")
    ap.add_argument("--dry-run", action="store_true", help="print routing + plan, invoke nothing")
    ap.add_argument("--yes", action="store_true", help="skip the interactive start confirmation")
    args = ap.parse_args(argv)

    sprint: Path = args.sprint
    state_path = sprint / "STATE.json"
    tickets_dir = sprint / "tickets"
    if not state_path.exists():
        print(f"BLOCKED: no STATE.json at {state_path}", file=sys.stderr)
        return 2

    # Resolve the claude CLI to an absolute path so subprocess (no shell) can find it even
    # when the launching shell's PATH lacks ~/.local/bin etc.
    args.cli = resolve_cli(args.cli)
    if not (shutil.which(args.cli) or Path(args.cli).exists()):
        print(f"BLOCKED: claude CLI not found ({args.cli!r}). "
              f"Pass --cli /path/to/claude (e.g. ~/.local/bin/claude).", file=sys.stderr)
        return 2

    state = load_json(state_path)
    order = ticket_order(state, sprint)
    accepted = accepted_set(state)
    completed = completed_set(state)
    implemented = set(state.get("implemented_awaiting_validation") or [])

    # build the work list with routing preview
    rows = []
    for tid in order:
        if args.only and tid not in args.only:
            continue
        tp = tickets_dir / f"{tid}.md"
        ec = parse_exec_class(tp) if tp.exists() else "?"
        deps = parse_dependencies(tp) if tp.exists() else []
        if tid in accepted:
            status = "accepted"
        elif tid in implemented:
            status = "implemented"
        elif tid in completed:
            status = "completed"
        else:
            status = "pending"
        dep_ok = all(d in accepted for d in deps)
        rows.append((tid, ec, status, deps, dep_ok,
                     engineer_alias(ec), auditor_alias(ec), VALIDATOR_TICKET_ALIAS))

    print("Sprint runner — routing plan:")
    print(f"{'ticket':8} {'class':20} {'status':12} {'eng':14} {'aud':14} {'val':10} deps")
    for tid, ec, status, deps, dep_ok, ea, aa, va in rows:
        flag = "" if dep_ok or status == "accepted" else "  (deps not accepted)"
        print(f"{tid:8} {ec:20} {status:12} {ea:14} {aa:14} {va:10} {','.join(deps) or '-'}{flag}")

    if args.dry_run:
        print("\n--dry-run: not invoking claude.")
        return 0

    todo = [r for r in rows if r[2] not in ("accepted", "completed")]
    if not todo:
        print("\nAll selected tickets are accepted or completed. Nothing to do.")
        # final gate
        print("\n=== FINAL GATE (opus/max) ===")
        v, r = validator_gate(f"sprint {sprint} final", sprint, permission_mode=args.permission_mode,
                              per_call_timeout=args.per_call_timeout, cli=args.cli)
        print(f"FINAL: {v} | {r}")
        return 0 if v == "GO" else 3

    if not args.yes:
        print(f"\nAbout to drive {len(todo)} ticket(s) autonomously in YT_TEST_MODE=1 "
              f"(permission-mode={args.permission_mode}). Ctrl-C to abort. Enter to proceed, n to stop: ",
              end="", flush=True)
        try:
            if input().strip().lower().startswith("n"):
                print("aborted."); return 1
        except EOFError:
            pass

    kw = dict(permission_mode=args.permission_mode, per_call_timeout=args.per_call_timeout, cli=args.cli)

    # group by wave for wave-gate stops
    wave_of = {}
    for w in ("W1", "W2", "W3"):
        for t in state.get("waves", {}).get(w, {}).get("tickets", []):
            wave_of[t] = w

    for tid, ec, status, deps, dep_ok, *_ in rows:
        if status in ("accepted", "completed"):
            print(f"\n[skip] {tid}: already {status}.")
            continue
        if not dep_ok:
            print(f"\n[skip] {tid}: dependencies not yet accepted ({deps}); will retry later.")
            continue
        result = process_ticket(tid, sprint, max_cycles=args.max_cycles,
                                skip_engineer=(status == "implemented"), **kw)
        if result == "ACCEPTED":
            # re-read state (the validator updated STATE.json)
            state = load_json(state_path)
            accepted = accepted_set(state)
            continue
        # STOP — critical user input required
        print(f"\n================ RUNNER HALTED ================\n{result}\n"
              f"(Re-run the same command after resolving to resume from STATE.json.)",
              flush=True)
        return 4 if result.startswith("STOP:HUMAN_REQUIRED") else 5

    # All selected tickets accepted → wave-gate validation (opus/max), stop for user review.
    done_waves = {wave_of.get(r[0]) for r in rows if r[2] == "accepted"}
    for w in sorted(x for x in done_waves if x):
        print(f"\n=== WAVE {w} GATE (opus/max) — independent validation ===")
        v, r = validator_gate(f"Wave {w}", sprint, **kw)
        print(f"WAVE {w}: {v} | {r}")
        if v != "GO":
            print(f"Wave {w} gate not GO — stopping for user review. Resolve and re-run.", flush=True)
            return 6

    print("\nAll selected tickets accepted and wave gates passed. "
          "Any real paid run (gate_a_spend) requires your explicit approval — not automated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
