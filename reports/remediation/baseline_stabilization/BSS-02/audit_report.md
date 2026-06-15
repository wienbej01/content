# BSS-02 Audit Report

**Ticket:** Storyboard and compile errors must fail before writing production JSON. Diagnostic files written instead.
**Date:** 2026-06-14
**Auditor:** Kiro (read-only validation)
**Verdict:** PASS

---

## Scope

Verify that `step_storyboard_create` and `step_compile_media_plan` in `scripts/produce.py`:

1. Raise `RuntimeError` BEFORE writing production JSON (`storyboard.json` / `media_plan.json`) when errors are present.
2. Write diagnostic artifacts (`storyboard_errors.json` / `media_plan_errors.json`) on failure.
3. Preserve any existing valid production artifact on error (no overwrite).

---

## Code Review Findings

### `step_storyboard_create` (line 222, produce.py)

Control flow on error path:
```
errors = result.get("errors", [])
if errors:
    diag = {"errors": ..., "warnings": ..., "beat_count": ...}
    (project_dir / "storyboard_errors.json").write_text(...)   # diagnostic WRITTEN
    raise RuntimeError(...)                                     # FAIL before write
(project_dir / "storyboard.json").write_text(...)              # only reached if no errors
```

**Correct.** The `storyboard.json` write is unreachable when errors exist. Diagnostic is written before the raise. Any pre-existing `storyboard.json` is untouched.

### `step_compile_media_plan` (line 321, produce.py)

Control flow on error path:
```
plan, errors = compile_plan(...)
if errors:
    diag = {"errors": errors, "beat_count": ...}
    (project_dir / "media_plan_errors.json").write_text(...)   # diagnostic WRITTEN
    raise RuntimeError(...)                                     # FAIL before write
(project_dir / "media_plan.json").write_text(...)              # only reached if no errors
```

**Correct.** Same pattern: production write is gated behind a clean error list. Diagnostic written before raise.

---

## Test Coverage

| Test | Asserts |
|------|---------|
| `test_storyboard_errors_block_step` | RuntimeError raised; `storyboard.json` does NOT exist; `storyboard_errors.json` written with correct content |
| `test_storyboard_valid_writes_json` | No raise; `storyboard.json` written with correct beats |
| `test_existing_storyboard_not_overwritten_on_error` | Pre-existing `storyboard.json` preserved after error |
| `test_compile_errors_block_step` | RuntimeError raised; `media_plan.json` does NOT exist; `media_plan_errors.json` written |
| `test_compile_valid_writes_json` | No raise; `media_plan.json` written with correct content |

All 5 tests pass. Coverage addresses all three acceptance criteria.

---

## Conclusion

The fail-closed pattern is correctly implemented. Errors are detected and raised before any production artifact write. Diagnostic files provide debuggability. Existing artifacts are preserved on failure.
