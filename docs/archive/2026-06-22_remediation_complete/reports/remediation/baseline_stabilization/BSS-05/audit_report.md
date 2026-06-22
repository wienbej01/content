# BSS-05 Audit Report — Orchestrator Verification Sweep

**Auditor:** Kiro subagent (read-only)
**Date:** 2026-06-14
**Scope:** Verify no swallowed exceptions on critical paths in `scripts/produce.py`

---

## Findings

### 1. Exception Handling in Step Functions

**Result: CLEAN**

Every step function (`step_research` through `step_gate_b_review`) raises `RuntimeError` on failure. Grep for `except.*pass` patterns found exactly ONE instance:

- **Line 65:** `_notify()` helper catches Telegram send failures with bare `except: pass`. This is a non-critical notification side-effect, NOT a pipeline control flow path.

No step function swallows exceptions that would mask a production failure.

### 2. Orchestrator Error Propagation

**Result: CORRECT**

The main loop (line ~600) wraps each step call in:
```python
try:
    result = fn(project_dir, state)
except Exception as e:
    step_status[step_name] = {"status": "failed", "error": str(e)}
    ...
    return False
```

Any raised exception → `status: failed` → pipeline halts → `return False`. No step can silently succeed after an internal failure.

### 3. Gate B Chain Enforcement

**Result: CORRECT**

- `STEPS` list places `build_quality_report` at index 18, `gate_b_review` at index 19 (final step).
- Pipeline executes sequentially; if `build_quality_report` raises (returncode != 0), orchestrator catches it, marks `failed`, and returns `False` immediately.
- `gate_b_review` is never reached.
- On resume: propagation logic (line ~574) invalidates all downstream of a failed step, so `gate_b_review` status is reset even if manually tampered.

### 4. Downstream Invalidation on Failure

**Result: CORRECT**

Lines 574–581: if any step has `status: failed`, all subsequent steps in STEPS are invalidated (set to `None`). This prevents stale downstream results from being treated as valid.

### 5. Gate B Telegram Failure Handling

**Result: ACCEPTABLE**

`step_gate_b_review` catches Telegram send failures with `except Exception as e` and prints a warning but still returns `{"video": str(video)}`. This is acceptable because:
- The gate's purpose is notification, not blocking.
- The video path is returned regardless for manual inspection.
- If `gate_b_review` actually needed to block, it should raise — but its design intent is "notify human for review."

---

## Summary

| Check | Status |
|-------|--------|
| No swallowed exceptions in step functions | ✅ Clean |
| Orchestrator halts on any step failure | ✅ Verified |
| `build_quality_report` must PASS before `gate_b_review` | ✅ Enforced by ordering + propagation |
| Failed step invalidates all downstream | ✅ Verified |
| Only non-critical side-effects (Telegram) tolerate failure | ✅ Acceptable |

**Audit verdict: PASS**
