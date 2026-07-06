# 04 Pass Gates

Each ticket must satisfy every gate before the Loop Controller may issue
`PASS_TO_NEXT_TICKET`.

## Per-ticket gates (all tickets)

- **G-FORENSIC**: A forensic report exists that names the exact defect class
  (per 02_FAILURE_TAXONOMY), cites the proof artifact/code line, and states
  what counts as success.
- **G-EVAL-BEFORE**: An eval-before exists, reproduces the defect (or proves
  the absence of required evidence), and is deterministic.
- **G-ENGINEERING**: An implementation report exists. The change set is diffed
  and verified against the ticket scope. No file outside scope is modified.
  No paid call path exists.
- **G-AUDIT**: An audit report exists with no `BLOCKER` or `MAJOR` findings.
  All DDL-* invariants are re-verified.
- **G-VALIDATION**: The validator ran all commands independently, confirmed the
  eval-after, and reported findings with attached logs.
- **G-TESTS**: The 5-file PPQ invariant suite passes (`INV-1`).
- **G-COMMIT**: After validation PASS, git commit with conventional commit
  prefix and imperative subject.

## Loop-level gates (checked at DDL-W5 closing)

- **G-LOOP-1**: `prod_4e0ce12e` assemblable with the feedback loop closed and
  NO DB-side duration patching. All deltas in the current active unit set are
  either accepted, trimmed, extended, or have blocking change requests.
- **G-LOOP-2**: Aggregate tolerance tightened to `1/FPS`. Re-run assembly
  preflight or the duration-logic unit test to confirm the new gate would
  catch a 2.9s drift.
- **G-LOOP-3**: The legacy fallback-3.0s check still exists as a named
  consistency guard, not as a quality gate. It fails to `BLOCKED` rather than
  silently accepting drift within its band.

## Gating levels (used in audit)

```text
BLOCKER: cannot proceed; fix required before any validation
MAJOR  : must fix before validation
MINOR  : can proceed if documented in residual risks
NIT    : style or commentary only
```

## Prohibited actions at any gate

- Weakening a numeric threshold in `configs/lipsync_thresholds.yaml`,
  `scripts/assemble.py`, or `scripts/assemble_db.py`.
- Adding a `try/except pass` around a gate that previously failed.
- Replacing a deterministic test with a skip or `xfail`.
- Marking a gate PASS when the underlying evidence shows FAIL.
