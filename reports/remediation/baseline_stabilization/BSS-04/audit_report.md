# BSS-04 Audit Report — Manifest Hardening

**Date:** 2026-06-14
**Auditor:** Kiro (read-only)
**Scope:** scripts/build_manifest.py, scripts/produce.py, tests/test_manifest_builder.py

---

## Criteria Checked

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No `--allow-missing` in production path | ✅ PASS | `produce.py:step_build_manifest` calls `build_manifest.py <project_dir>` without `--allow-missing`. The flag exists in CLI for dev use but is never passed by the orchestrator. |
| 2 | No TKT-10/TKT-11 pending warnings | ✅ PASS | `grep -n 'TKT-10\|TKT-11\|pending' scripts/build_manifest.py` returns no matches. |
| 3 | Music path is deterministic from config | ✅ PASS | `load_music_config()` reads `constraints.json → music.default_path` (currently `brand/music/night_snow.mp3`). No glob, scandir, iterdir, or sorted-directory patterns present. |
| 4 | Format field present in manifest output | ✅ PASS | Line 200: `"format": format_str` in manifest dict. Format resolved from `state.json` or defaults to `"short"`. |
| 5 | All tests pass | ✅ PASS | 372 tests passed (including 11 manifest tests, 5 BSS-04-specific). 0 failures. |

---

## Detailed Findings

### 1. --allow-missing retained as CLI flag (acceptable)

`build_manifest.py` still accepts `--allow-missing` as an argparse option (line 217). This is acceptable because:
- The production orchestrator (`produce.py:step_build_manifest`) invokes it WITHOUT the flag.
- A dedicated test (`test_no_allow_missing_in_production_call`) asserts the flag is absent from the production call path.
- The flag remains useful for developer debugging during generation iterations.

### 2. Music determinism

Music resolution path: `constraints.json` → `music.default_path` → resolve against repo root → validate existence → include in manifest with `volume_db`, `fade_in_sec`, `fade_out_sec`.

If the configured file is missing and the format is in `required_for_formats`, build returns a hard error. No fallback. No directory scanning.

### 3. Format field

The manifest includes a top-level `"format"` key resolved from:
1. Explicit `--format` CLI arg (if provided)
2. `state.json → format` (if file exists)
3. Default `"short"`

### 4. Test coverage

BSS-04-specific tests:
- `test_no_allow_missing_in_production_call` — source-level assertion
- `test_music_uses_configured_path` — functional test with fixtures
- `test_music_nondeterministic_directory_scan_rejected` — negative test ensuring no glob patterns
- `test_required_music_missing_is_error` — validates hard-fail on missing required music
- `test_format_in_manifest` — asserts top-level format key in output

---

## Conclusion

All five BSS-04 requirements verified. No issues found.
