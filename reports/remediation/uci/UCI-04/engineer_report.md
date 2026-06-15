# UCI-04 Engineer Report — assemble reads clip paths from clip DB

**Date:** 2026-06-15
**Status:** ✅ COMPLETE — all acceptance criteria met

---

## Changes made

### `scripts/assemble.py`

1. **Import:** Added `import clip_db` alongside existing pipeline imports.

2. **UCI-04 gate block** (inserted after manifest validation, before music overrides):
   - Checks if any segment carries a `clip_id`.
   - If yes: initializes DB, checks if project has registered clips.
   - If clips are registered: resolves each segment's `media` field from `clip_db.get_path(clip_id)` (DB is golden truth), then calls `clip_db.assert_all_valid(project_id)`. Assembly FAILS with an actionable list if any clip is not valid or has open change requests.
   - If clip_ids are present but no clips registered in DB: emits a transitional warning (e2e/early-pipeline case where DB hasn't been populated yet).
   - If no clip_ids in manifest: emits a legacy-mode warning and skips entirely.

3. **Zero changes** to existing assembly logic (lipsync keep-audio, continuous voiceover, music bed, overlays, stream-integrity checks, speed alignment).

### `tests/test_uci04_assemble_db.py` (5 tests)

| Test | Validates |
|------|-----------|
| `test_assemble_resolves_path_from_db` | clip_id segment resolves media via DB, not manifest field |
| `test_assemble_blocked_when_clip_not_valid` | 'ordered' status clip → RuntimeError with actionable list |
| `test_assemble_blocked_on_change_request` | valid clip + open change request → RuntimeError |
| `test_assemble_proceeds_when_all_valid` | all clips valid → assembly produces output |
| `test_legacy_manifest_no_clipid_skips_db_gate` | no clip_ids → backward compat + UserWarning |

---

## Acceptance criteria verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | assemble resolves media path from clip_db when clip_id present | ✅ Proven by `test_assemble_resolves_path_from_db` |
| 2 | assert_all_valid gate runs before mux; blocks on any non-valid clip | ✅ Proven by `test_assemble_blocked_when_clip_not_valid` + `test_assemble_blocked_on_change_request` |
| 3 | Legacy manifests (no clip_id) still assemble (backward compat) | ✅ Proven by `test_legacy_manifest_no_clipid_skips_db_gate` + all 17 existing `test_assemble.py` tests pass |
| 4 | Existing assembly behavior preserved | ✅ All 17 `test_assemble.py` tests pass unchanged |
| 5 | All tests pass; full suite green | ✅ 625 passed, 0 failed |

---

## Test output

```
tests/test_uci04_assemble_db.py — 5 passed
tests/test_assemble.py — 17 passed (10 warnings: legacy-mode, expected)
Full suite: 625 passed, 12 warnings in 144.81s
```

---

## Design decisions

1. **DB initialization in assemble:** `clip_db.init_db()` is called to ensure tables exist before querying. This avoids "no such table" errors when the DB file exists (from CLIP_DB_PATH) but hasn't been initialized.

2. **Transitional fallback:** When clip_ids exist in the manifest but no clips are registered in the DB for the project, the gate is skipped with a warning. This handles the pipeline-in-transition case (e.g., e2e tests or projects that haven't run `order_clip` yet).

3. **Path resolution fallback:** If `clip_db.get_path(cid)` returns None (clip not in DB), the manifest's original `media` field is preserved. The gate only blocks on clips that ARE registered but NOT valid.

4. **project_id derivation:** Uses `manifest["id"]` (the standard field), falls back to manifest's parent directory name.
